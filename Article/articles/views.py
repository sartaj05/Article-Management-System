from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework import status
from .models import Article, Tag, Category, Comment
from .serializers import ArticleSerializer, TagSerializer, CategorySerializer, CommentSerializer
from .permissions import IsEditorOrAdmin, IsJournalist
from rest_framework.decorators import api_view, permission_classes
from rest_framework.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST

# View for Journalist Dashboard
def journalist_dashboard(request):
    return render(request, 'articles/journalist_dashboard.html')

# View for Editor Dashboard
def editor_dashboard(request):
    return render(request, 'articles/editor_dashboard.html')

# View for Admin Dashboard
def admin_dashboard(request):
    return render(request, 'articles/admin_dashboard.html')

# Article Create View (Handles Article Creation)
class ArticleCreateView(CreateAPIView):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsEditorOrAdmin]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

# Article List View (Lists Articles based on User Role)
class ArticleListView(ListAPIView):
    serializer_class = ArticleSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'Journalist':
            return Article.objects.filter(author=user)
        elif user.role in ['Editor', 'Admin']:
            return Article.objects.all()
        return Article.objects.none()

# Article Detail View (Retrieve, Update, Delete Articles)
class ArticleDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsEditorOrAdmin]

    def perform_update(self, serializer):
        # Allow Editors/Admins to modify articles
        serializer.save()

# Tag List View (Lists Tags)
class TagListView(ListAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

# Category List View (Lists Categories)
class CategoryListView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

# Comment List and Create View (Lists and Creates Comments for Articles)
class CommentListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, article_id):
        comments = Comment.objects.filter(article_id=article_id)
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    def post(self, request, article_id):
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user, article_id=article_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsJournalist])  # Ensure only Journalists can submit
def submit_article(request):
    """
    API endpoint to submit an article.
    """
    # Instantiate the serializer with the incoming data and the request context
    serializer = ArticleSerializer(data=request.data, context={'request': request})

    # Check if the serializer is valid
    if serializer.is_valid():
        # Save the article and link it to the current user (journalist)
        serializer.save(author=request.user)
        return Response(
            {'message': 'Article submitted successfully', 'article': serializer.data},
            status=HTTP_201_CREATED
        )
    
    # If validation fails, return the error response
    return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)
