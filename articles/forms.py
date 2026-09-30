from django import forms
from .models import Article, Comment
from django.utils.timezone import now

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            'title', 
            'subtitle', 
            'content', 
            'author_name', 
            'email', 
            'image', 
            'tags', 
            'category', 
            'publish_date', 
            'agreed_to_terms',
        ]
        widgets = {
            'publish_date': forms.DateInput(attrs={'type': 'date'}),
            'content': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Write your article content here...'}),
            'tags': forms.SelectMultiple(attrs={'class': 'select-multiple'}),
            'category': forms.Select(attrs={'class': 'select-category'}),
        }

    def clean_publish_date(self):
        """
        Ensures that the publish date is in the future.
        """
        publish_date = self.cleaned_data.get('publish_date')
        if publish_date and publish_date <= now().date():
            raise forms.ValidationError('Publish date must be in the future.')
        return publish_date

    def clean_agreed_to_terms(self):
        """
        Ensures that the user has agreed to the terms.
        """
        agreed_to_terms = self.cleaned_data.get('agreed_to_terms')
        if not agreed_to_terms:
            raise forms.ValidationError('You must agree to the terms before submitting.')
        return agreed_to_terms

    def clean_email(self):
        """
        Validates the email field.
        """
        email = self.cleaned_data.get('email')
        if email and not email.endswith('@example.com'):  # Example validation
            raise forms.ValidationError('Please use a valid company email address.')
        return email

    def clean_tags(self):
        """
        Allows comma-separated tags and converts them to a list of strings.
        """
        tags = self.cleaned_data.get('tags')
        if tags:
            tags = [tag.strip() for tag in tags.split(',')]
        return tags

    def clean_category(self):
        """
        Ensures that category is provided as text, and converts it to a string.
        """
        category = self.cleaned_data.get('category')
        if category:
            category = category.strip()
        return category


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['author', 'content', 'article']  # Adjust fields based on your model

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the initial value for the author field to the currently logged-in user
        if 'user' in kwargs:
            self.fields['author'].initial = kwargs['user']

    def save(self, commit=True):
        comment = super().save(commit=False)
        if not comment.author:  # Ensure author is set to the current user
            comment.author = self.instance.user  # or `request.user` if available
        if commit:
            comment.save()
        return comment
