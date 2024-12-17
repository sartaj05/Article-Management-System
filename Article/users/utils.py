from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

def get_tokens_for_user(user):
    """
    Generate and return a dictionary containing access and refresh tokens for the given user.
    """
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }

def validate_token(token):
    """
    Validate the provided JWT token.

    Args:
        token (str): The JWT token to validate.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    try:
        RefreshToken(token)  # Attempt to decode the token
        return True
    except TokenError:
        return False

def validateall(validated_data):
    """
    Perform custom validation on the provided data.

    Args:
        validated_data (dict): The data to validate.

    Returns:
        dict: Validation result with 'result' (bool) and errors (if any).
    """
    errors = {}

    # Validate 'username'
    if not validated_data.get('username'):
        errors['username'] = 'This field is required.'

    # Validate 'email'
    if not validated_data.get('email'):
        errors['email'] = 'This field is required.'

    # Validate 'password' (example: check minimum length)
    password = validated_data.get('password')
    if password and len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters long.'

    # Add any other custom validations as needed...

    return {"result": not bool(errors), "errors": errors}
