# View for Journalist Dashboard
def journalist_dashboard(request):
    return render(request, 'articles/journalist_dashboard.html')

# View for Editor Dashboard
def editor_dashboard(request):
    return render(request, 'articles/editor_dashboard.html')

# View for Admin Dashboard
def admin_dashboard(request):
    return render(request, 'articles/admin_dashboard.html')

# def journalist_dashboard(request):
#     return render(request, 'journalist_dashboard.html')
from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.test import tag
from django.urls import reverse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Article, Comment, Like, ArticleView,Category
from rest_framework.views import APIView
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.generics import CreateAPIView
from rest_framework import status
from .serializers import ArticleSerializer
from .forms import ArticleForm
from django.db.models import Q
from django.core.paginator import Paginator
from rest_framework import generics
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.pagination import PageNumberPagination
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from articles.models import Article
from users.models import CustomUser

class ArticleListAPIView(generics.ListAPIView):
    # queryset = Article.objects.filter(is_visible=True).order_by('-created_at')
    queryset = Article.objects.order_by('-created_at')
    serializer_class = ArticleSerializer

def user_profile(request):
    # Return user profile data
    return JsonResponse({'username': 'JohnDoe', 'email': 'john@example.com'})
class ArticleCountAPIView(APIView):
    def get(self, request):
        article_count = Article.objects.count()  # Get the count of articles
        return Response({'article_count': article_count})

class ArticlePagination(PageNumberPagination):
    page_size = 10  # Number of articles per page
    page_size_query_param = 'page_size'  # Allows clients to specify a different page size
    max_page_size = 100  # Max limit for page size

class ArticleCreateAPIView(CreateAPIView):
    queryset = Article.objects.all()  
    serializer_class = ArticleSerializer 
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        # Filter articles to only include those with publish_date in the present or future
        return Article.objects.filter(publish_date__gte=now())  # Ensure only authenticated users can create articles

from django.utils.timezone import now
class ArticleDetailView(View):
    permission_classes = [IsAuthenticated]

    def get(self, request, article_id):
        # Manually authenticate the user based on the JWT token in the Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', None)
        if not auth_header:
            return JsonResponse({'error': 'Authorization token required'}, status=401)

        try:
            # Extract the token from the header
            token = auth_header.split(' ')[1]  # Format should be "Bearer <token>"
            authentication = JWTAuthentication()

            # Use the JWTAuthentication's authenticate method to authenticate the user
            user, _ = authentication.authenticate(request)
            request.user = user
        except (IndexError, AuthenticationFailed) as e:
            return JsonResponse({'error': str(e)}, status=401)

        # Fetch the article by article_id
        article = get_object_or_404(Article, id=article_id)
        
        # Log the view (if user is authenticated)
        ArticleView.objects.create(article=article, user=request.user)

        # Prepare the data for JSON response
        article_data = {
            'id': article.id,
            'title': article.title,
            'subtitle': article.subtitle,
            'content': article.content,
            'author': article.author.username,
            'tags': article.tags.split(',') if article.tags else [],
            'category': article.category,
            'publish_date': article.publish_date,
            'summary': article.summary,
            'status': article.status,
            'is_visible': article.is_visible,
            'created_at': article.created_at,
            'updated_at': article.updated_at,
        }

        return JsonResponse(article_data, status=200)



        # return render(request, 'articles/article_detail.html', context)

class ArticleSearchView(View):
    def get(self, request):
        # Manually authenticate the user based on the JWT token in the Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', None)
        if not auth_header:
            return JsonResponse({'error': 'Authorization token required'}, status=401)

        try:
            # Extract the token from the header
            token = auth_header.split(' ')[1]  # Format should be "Bearer <token>"
            authentication = JWTAuthentication()  # Use JWTAuthentication

            # Authenticate the user based on the token
            user, _ = authentication.authenticate(request)  # Use authenticate method
            request.user = user
        except (IndexError, AuthenticationFailed):
            return JsonResponse({'error': 'Invalid or missing token'}, status=401)

        # Fetch the search query from the URL parameters
        query = request.GET.get('q', '')

        # Filter articles based on query in title, content, tags, or category
        if request.user.role == 'Journalist':
            # For journalists, only fetch their own articles
            articles = Article.objects.filter(
                Q(title__icontains=query) | 
                Q(content__icontains=query) |
                Q(tags__icontains=query) | 
                Q(category__icontains=query),
                author=request.user  # Only fetch articles written by the logged-in user
            ).order_by('-created_at')
        else:
            # For admin and editor, fetch all articles
            articles = Article.objects.filter(
                Q(title__icontains=query) | 
                Q(content__icontains=query) |
                Q(tags__icontains=query) | 
                Q(category__icontains=query)
            ).order_by('-created_at')

        # Paginate the results
        paginator = Paginator(articles, 10)  # Show 10 articles per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Serialize the articles
        serializer = ArticleSerializer(page_obj, many=True)

        # Prepare the paginated response (including page and total pages)
        response_data = {
            'articles': serializer.data,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
        }

        # Return the response in JSON format
        return JsonResponse(response_data, status=200)

class CategoryArticleListView(View):
    def get(self, request, category_name):
        # Manually authenticate the user based on the JWT token in the Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', None)
        if not auth_header:
            return JsonResponse({'error': 'Authorization token required'}, status=401)

        try:
            # token = auth_header.split(' ')[1]  # Format should be "Bearer <token>"
            authentication = JWTAuthentication()  # Use JWTAuthentication from simplejwt
            user, _ = authentication.authenticate(request)  # This is the correct method to authenticate
            request.user = user
        except (IndexError, AuthenticationFailed):
            return JsonResponse({'error': 'Invalid or missing token'}, status=401)

        # Filter articles by category (using the predefined category field)
        articles = Article.objects.filter(is_visible=True, category=category_name)
        
        # Prepare the list of articles to make it JSON serializable
        article_data = []
        for article in articles:
            article_data.append({
                'id': article.id,
                'title': article.title,
                'subtitle': article.subtitle,
                'content': article.content,
                'author': article.author.username,  # Assuming the author is a User object
                'tags': article.tags.split(',') if article.tags else [],
                'category': article.category,
                'publish_date': article.publish_date,
                'summary': article.summary,
                'status': article.status,
                'is_visible': article.is_visible,
                'created_at': article.created_at,
                'updated_at': article.updated_at,
            })
        
        # Prepare the context for the JSON response
        respond_data = {
            'category': category_name,
            'articles': article_data
        }

        return JsonResponse(respond_data, status=200)


# Helper function to check user permissions
def user_is_author(user, article):
    return article.author == user


class ArticleUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def has_edit_permission(self, user, article):
        """
        Checks if the user has permission to edit the article.
        - Admin and Editor can edit all articles.
        - Journalists can only edit their own articles.
        """
        if user.role in ['Admin', 'Editor']:
            return True
        if user.role == 'Journalist' and article.author == user:
            return True
        return False

    def get(self, request, article_id):
        """
        Fetch article details for editing (GET).
        """
        # Fetch the article by its ID
        article = get_object_or_404(Article, id=article_id)

        # Check if the user has permission to view the article
        if not self.has_edit_permission(request.user, article):
            return Response({'error': 'You do not have permission to view or edit this article.'}, status=403)

        # Serialize the article details
        article_data = ArticleSerializer(article).data
        return Response({'article': article_data}, status=200)

    def put(self, request, article_id):
        """
        Handles full update (PUT) of an article. All fields must be provided.
        """
        # Fetch the article by its ID
        article = get_object_or_404(Article, id=article_id)

        # Check if the user has permission to edit the article
        if not self.has_edit_permission(request.user, article):
            return Response({'error': 'You do not have permission to edit this article.'}, status=403)

        # Pass the request context to the serializer
        serializer = ArticleSerializer(article, data=request.data, context={'request': request})

        if serializer.is_valid():
            # Save the updated article
            serializer.save()

            # Return the updated article data
            return Response({'article': serializer.data}, status=200)

        # If serializer is invalid, return the validation errors
        return Response({'errors': serializer.errors}, status=400)

    def patch(self, request, article_id):
        """
        Handles partial update (PATCH) of an article. Only provided fields are updated.
        """
        # Fetch the article by its ID
        article = get_object_or_404(Article, id=article_id)

        # Check if the user has permission to edit the article
        if not self.has_edit_permission(request.user, article):
            return Response({'error': 'You do not have permission to edit this article.'}, status=403)

        # Pass the request context to the serializer for partial update
        serializer = ArticleSerializer(article, data=request.data, partial=True, context={'request': request})

        if serializer.is_valid():
            # Save the updated article
            serializer.save()

            # Return the updated article data
            return Response({'article': serializer.data}, status=200)

        # If serializer is invalid, return the validation errors
        return Response({'errors': serializer.errors}, status=400)

class ArticleDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, article_id):
        # Fetch the article by its ID
        article = get_object_or_404(Article, id=article_id)

        # Check if the logged-in user is the author or has permission to delete
        if request.user != article.author:
            return Response({'error': 'You do not have permission to delete this article'}, status=403)

        # Delete the article
        article.delete()

        return Response({'message': 'Article deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class ArticleApproveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        # Fetch the article by its ID
        article = get_object_or_404(Article, id=pk)

        # Check if the user has the required role (Editor or Admin)
        if request.user.role not in ['Editor', 'Admin']:
            return Response({'error': 'You do not have permission to approve this article'}, status=403)

        # Check if the article is already approved
        if article.status == "Approved":
            return Response({'error': 'This article is already approved'}, status=400)

        # Mark the article as approved
        article.status = "Approved"
        email = article.email
        approver_username = request.user.username  # Get the username of the user who approved
        article.save()

        # Send a success email notification to the article author
        send_mail(
            subject="Article Approved",
            message=f"Your article has been approved successfully by {approver_username}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response({'message': 'Article approved successfully.'}, status=status.HTTP_200_OK)
    

class ArticlePublishedView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id):
        # Fetch the article by its ID
        article = get_object_or_404(Article, id=article_id)

        # Check user role
        if request.user.role not in ['Editor', 'Admin']:
            return Response(
                {'error': 'You do not have permission to publish this article'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if the article is already published
        if article.status == "published":
            return Response(
                {'error': 'This article is already published.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update the article status
        article.status = "published"
        article.publish_date = timezone.now()
        article.save()

        # Send email notification to the article author
        if article.email:
            send_mail(
                subject="Article Published",
                message=f"Your article '{article.title}' has been published successfully.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[article.email],
                fail_silently=True,
            )

        return Response(
            {'message': 'Article published successfully.', 'status': 'published'},
            status=status.HTTP_200_OK
        )


    def get(self, request, article_id=None):
        # Check if the user has the required role (Editor or Admin)
        if request.user.role not in ['Editor', 'Admin']:
            return Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )
      
        if article_id:
            # Fetch a single published article
            article = get_object_or_404(Article, id=article_id, status='published')  # Ensure 'status' field exists
            article_data = {
            "id": article.id,
            "title": article.title,
            "content": article.content,  # Add content field
            "tags": article.tags,  # Add tags field
            "email": article.author.email if article.author else None,  # Add author email
            "subtitle": article.subtitle,  # Add subtitle field
            "category": article.category,
            "publish_date": article.publish_date,
            "status": article.status,
            "image": article.image,
        }
            return Response(article_data)

        # Fetch all published articles
        published_articles = Article.objects.filter(status='published').order_by('-publish_date')  # Adjust as needed
        serializer = ArticleSerializer(published_articles, many=True)
        return Response({"published_articles": serializer.data})
        

class PendingApprovalArticleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Assuming the article has a status field that tracks approval
        pending_articles = Article.objects.filter(status='pending_approval')  # Replace with actual status logic
        serializer = ArticleSerializer(pending_articles, many=True)
        return Response({'articles': serializer.data})


class ArticleImageGalleryView(View):
    def get(self, request, slug):
        article = get_object_or_404(Article, slug=slug)
        images = article.images.all()
        context = {'article': article, 'images': images}
        return render(request, 'articles/article_gallery.html', context)    

class SubmitArticleAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            # Validate required fields
            required_fields = ['title', 'content', 'email', 'category', 'publish_date']
            for field in required_fields:
                if field not in data:
                    return Response({'error': f'{field} is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate category
            try:
                category = Category.objects.get(id=data['category'])
            except Category.DoesNotExist:
                return Response({'error': 'Invalid category ID.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate publish_date (must be in the future)
            try:
                publish_date = datetime.strptime(data['publish_date'], '%Y-%m-%d').date()
                if publish_date <= datetime.today().date():
                    return Response({'error': 'Publish date must be in the future.'}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({'error': 'Invalid publish_date format. Please use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

            # Create article
            article = Article.objects.create(
                title=data['title'],
                subtitle=data.get('subtitle', ''),
                content=data['content'],
                author=request.user,
                email=data['email'],
                category=category,
                publish_date=publish_date
            )
            
            # Add tags if provided
            if 'tags' in data:
                tags = tag.objects.filter(id__in=data['tags'])
                if tags.exists():
                    article.tags.set(tags)
            
            # Handle image upload
            if 'image' in request.FILES:
                article.image = request.FILES['image']
                article.save()

            return Response({'message': 'Article created successfully!'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ArticleDraftsView(LoginRequiredMixin, View):
    def get(self, request):
        # Assuming 'is_draft' is a boolean field in your Article model to represent draft status
        drafts = Article.objects.filter(author=request.user, is_draft=True).order_by('-created_at')
        context = {'drafts': drafts}
        return render(request, 'articles/article_drafts.html', context)
class ArticleCommentsView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get(self, request, article_id):
        article = get_object_or_404(Article, id=article_id)
        comments = article.comments.all()
        context = {'article': article, 'comments': comments}
        return render(request, 'articles/article_comments.html', context)

    def test_func(self):
        article = get_object_or_404(Article, id=self.kwargs['article_id'])
        return article.author == self.request.user or self.request.user.role in ['Editor', 'Admin']
class ArticleArchiveView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get(self, request):
        archived_articles = Article.objects.filter(is_archived=True).order_by('-created_at')
        context = {'archived_articles': archived_articles}
        return render(request, 'articles/article_archive.html', context)

    def test_func(self):
        return self.request.user.role in ['Editor', 'Admin']
class ArticleStatusUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def post(self, request, article_id):
        article = get_object_or_404(Article, id=article_id)
        new_status = request.POST.get('status')  # Assuming 'status' is passed as a form field
        article.status = new_status
        article.save()
        return HttpResponseRedirect(reverse('articles:article-detail', args=[article.slug]))

    def test_func(self):
        article = get_object_or_404(Article, id=self.kwargs['article_id'])
        return self.request.user.role in ['Editor', 'Admin']

from django.shortcuts import render,redirect
class ArticleSubmitView(View):
    def get(self, request):
        form = ArticleForm()
        return render(request, 'articles/article_form.html', {'form': form})

    def post(self, request):
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user  # Make sure the article is saved under the logged-in user
            article.save()
            return redirect('articles:article-detail', slug=article.slug)
        return render(request, 'articles/article_form.html', {'form': form})

@login_required
def admin_dashboard_data(request):
    if request.user.role != 'Admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    total_articles = Article.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    pending_approvals = Article.objects.filter(status='Pending').count()

    return JsonResponse({
        'total_articles': total_articles,
        'active_users': active_users,
        'pending_approvals': pending_approvals
    })

@csrf_exempt
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def reject_article(request, article_id):
    # Check if the user is an Admin or Editor
    if not (request.user.is_staff or request.user.role == 'Editor'):
        return JsonResponse({"error": "You do not have permission to reject articles."}, status=403)

    # Get the article to reject
    article = get_object_or_404(Article, pk=article_id)

    # Handle already rejected or approved cases
    if article.status == 'rejected':
        return JsonResponse({"error": "This article has already been rejected."}, status=400)

    if article.status == 'approved':
        return JsonResponse({"error": "This article has already been approved and cannot be rejected."}, status=400)

    # Mark article as rejected
    article.status = 'rejected'
    article.save()

    return JsonResponse({"message": "Article rejected successfully."}, status=200)
# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Article
from .serializers import ArticleSerializer
from rest_framework import status

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Article
from .serializers import ArticleSerializer
from rest_framework import status

class PublishedArticleListView(APIView):
    # Remove authentication and permission classes to make it public
    permission_classes = []  # No authentication required

    def get(self, request):
        # Fetch all published articles
        published_articles = Article.objects.filter(status='published').order_by('-publish_date')
        
        # Paginate the results using the custom ArticlePagination class
        paginator = ArticlePagination()
        result_page = paginator.paginate_queryset(published_articles, request)
        
        # Serialize the paginated articles
        serializer = ArticleSerializer(result_page, many=True)
        
        # Return the paginated response with articles and pagination info
        return paginator.get_paginated_response(serializer.data)

from rest_framework.pagination import PageNumberPagination

class ArticlePagination(PageNumberPagination):
    page_size = 3  # Limit to 3 articles per page
    page_size_query_param = 'page_size'  # Allow clients to set page size (optional)
    max_page_size = 3  # Optional: Max page size limit (optional)
