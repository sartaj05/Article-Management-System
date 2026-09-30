from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.urls import reverse
from users.models import CustomUser as User, Profile
import re
from datetime import datetime
User = get_user_model()

# Profile Serializer
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['bio', 'profile_picture', 'contact_info']

    def to_representation(self, instance):
        return {
            'bio': instance.bio or '',
            'profile_picture': instance.profile_picture.url if instance.profile_picture else None,
            'contact_info': instance.contact_info or '',
        }
from rest_framework import serializers
from users.models import CustomUser  # Make sure this import is present
from rest_framework import serializers
from .models import CustomUser, Profile

class RegistrationSerializer(serializers.ModelSerializer):
    # Include profile as a nested serializer
    profile = serializers.JSONField(required=False)

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'password', 'role', 'checkbox', 'profile']
    
    def validate_email(self, value):
        # Check if the email already exists in the database
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value
    
    def create(self, validated_data):
        # Pop profile data if present
        profile_data = validated_data.pop('profile', None)
        
        # Create the user instance
        user = CustomUser.objects.create_user(
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            checkbox=validated_data.get('checkbox', False),
            role=validated_data.get('role', 'Journalist')
        )
        
        # If profile data is provided, create a profile for the user
        if profile_data:
            Profile.objects.create(user=user, **profile_data)
        
        return user

# Login Serializer
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=255)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if user is None:
            raise serializers.ValidationError("Invalid credentials")
        data['user'] = user
        return data

    def get_tokens_for_user(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

# User Serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'username', 'email', 'role']

# User Update Serializer
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

# Change Password Serializer
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        # This is where you can validate password complexity or any custom rules
        user = self.context['request'].user
        if not Validator.passwordvalidater(value, user.username, user.email):
            raise serializers.ValidationError("Password does not meet the required complexity.")
        return value

# Password Reset Serializer
class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user with this email found.")
        return value

    def save(self, request):
        user = User.objects.get(email=self.validated_data['email'])
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_url = request.build_absolute_uri(
            reverse('reset-password', kwargs={'uidb64': uid, 'token': token})
        )
        send_mail(
            subject='Password Reset Request',
            message=f'Click the link below to reset your password:\n\n{reset_url}',
            from_email='no-reply@example.com',
            recipient_list=[user.email],
        )

class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate(self, data):
        email = data.get('email')
        otp = data.get('otp')

        # Check if OTP exists in the session
        stored_otp = self.context['request'].session.get('otp')
        stored_otp_time = self.context['request'].session.get('otp_created_at')
        stored_email = self.context['request'].session.get('otp_email')

        if not stored_otp:
            raise serializers.ValidationError("OTP is expired or not generated.")
        
        if email != stored_email:
            raise serializers.ValidationError("The email address does not match the one used for OTP generation.")
        
        if otp != stored_otp:
            raise serializers.ValidationError("Invalid OTP.")

        # Check if OTP is expired (10 minutes expiry)
        otp_creation_time = datetime.fromisoformat(stored_otp_time)
        if (datetime.now() - otp_creation_time).total_seconds() > 600:  # 600 seconds = 10 minutes
            raise serializers.ValidationError("OTP has expired.")
        
        return data
    

    
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class PasswordResetWithOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    def validate_otp(self, value):
        """
        Validate the OTP from the session.
        """
        request = self.context.get('request')
        session_otp = request.session.get('otp')
        
        if not session_otp:
            raise serializers.ValidationError("OTP has expired or was not set.")
        
        if value != session_otp:
            raise serializers.ValidationError("Invalid OTP.")
        
        return value

    def validate_new_password(self, value):
        """
        Optionally add custom password validation logic here.
        """
        # Example: Check if the password contains both letters and numbers
        if not any(char.isdigit() for char in value) or not any(char.isalpha() for char in value):
            raise serializers.ValidationError("Password must contain both letters and numbers.")
        return value

    def update(self, instance, validated_data):
        """
        Update the user's password after validating OTP.
        """
        request = self.context.get('request')
        email = request.session.get('otp_email')
        
        if not email:
            raise serializers.ValidationError("No email found in session. Please request OTP again.")

        # Get the user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email.")

        # Update the password
        user.set_password(validated_data['new_password'])
        user.save()

        # Clear OTP-related session data
        request.session.pop('otp', None)
        request.session.pop('otp_email', None)
        request.session.pop('otp_created_at', None)

        return user


# Request OTP Serializer
class RequestOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user with this email found.")
        return value

# Validation Utilities
class Validator:
    @staticmethod
    def fnamevalidater(name):
        return bool(re.match(r'^[a-zA-Z]+(?: [a-zA-Z]+)*$', name.strip()))

    @staticmethod
    def lnamevalidater(name):
        return bool(re.match(r'^[a-zA-Z-]+(?: [a-zA-Z-]+)*$', name.strip()))

    @staticmethod
    def usernamevalidater(uname):
        return bool(re.fullmatch(r'^[a-zA-Z][a-zA-Z0-9._]{1,14}[a-zA-Z0-9]$', uname))

    @staticmethod
    def emailvalidater(email):
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.strip()))

    @staticmethod
    def passwordvalidater(password, username, email):
        if not re.match(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()_+={}\[\]:;"\'<>,.?/\\|`~\-]).{8,}$', password):
            return False
        if username.lower() in password.lower() or email.split('@')[0].lower() in password.lower():
            return False
        return True

def validateall(data):
    errors = {}

    if not Validator.fnamevalidater(data.get("first_name", "")):
        errors['first_name'] = 'Invalid first name.'

    if not Validator.lnamevalidater(data.get("last_name", "")):
        errors['last_name'] = 'Invalid last name.'

    if not Validator.usernamevalidater(data.get('username', "")):
        errors['username'] = 'Invalid username.'

    if not Validator.emailvalidater(data.get("email", "")):
        errors['email'] = 'Invalid email.'

    if not Validator.passwordvalidater(data.get("password", ""), data.get("username", ""), data.get("email", "")):
        errors['password'] = 'Invalid password.'

    return {"result": not errors, "errors": errors}
