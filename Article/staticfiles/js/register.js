document.getElementById('registration-form').addEventListener('submit', async function (e) {
    e.preventDefault();

    const form = e.target;
    const messageElement = document.getElementById('message');

    // Clear previous messages
    messageElement.textContent = "";

    // Clear all error messages and remove error class
    const errorFields = ['first_name', 'last_name', 'username', 'email', 'password', 'role', 'confirm_password', 'checkbox'];
    let firstInvalidField = null; // Reset invalid field tracker
    errorFields.forEach(field => {
        const errorElement = document.getElementById(`${field}_error`);
        errorElement.textContent = "";
        const inputField = document.getElementById(field);
        inputField.classList.remove('error');
    });

    let isValid = true;

    // Validate Fields (same as your existing validation logic)
    const firstName = document.getElementById('first_name').value.trim();
    if (firstName.length < 2 || firstName.length > 30) {
        isValid = false;
        showError('first_name', "First Name must be between 2 and 25 characters.");
    }

    const lastName = document.getElementById('last_name').value.trim();
    if (lastName && (lastName.length < 2 || lastName.length > 25)) {
        isValid = false;
        showError('last_name', "Last Name must be between 2 and 25 characters.");
    }

    const username = form.username.value.trim();
    if (username.length < 4) {
        isValid = false;
        showError('username', "Username must be at least 4 characters.");
    } else if (username.length > 20) {
        isValid = false;
        showError('username', "Username must not exceed 20 characters.");
    }

    const email = form.email.value.trim();
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(email)) {
        isValid = false;
        showError('email', "Please enter a valid email address.");
    }

    const password = form.password.value;
    const passwordRegex = /^(?=.*\d)(?=.*[a-zA-Z])(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
    if (!passwordRegex.test(password)) {
        isValid = false;
        showError('password', "Password must be at least 8 characters long, and include a number and a special character.");
    }

    // Confirm Password Validation
    const confirmPassword = form.confirm_password.value.trim();
    if (confirmPassword !== password) {
        isValid = false;
        document.getElementById('confirm_password_error').textContent = "Passwords do not match.";
        document.getElementById('confirm_password').classList.add('error');
    } else {
        document.getElementById('confirm_password_error').textContent = ''; // Clear error if passwords match
        document.getElementById('confirm_password').classList.remove('error');
    }

    const role = form.role.value;
    if (!role) {
        isValid = false;
        showError('role', "Please select a role.");
    }

    const checkbox = form.checkbox.checked;
    if (!checkbox) {
        isValid = false;
        showError('checkbox', "You must accept the Terms & Conditions.");
    }

    if (!isValid && firstInvalidField) {
        firstInvalidField.scrollIntoView({ behavior: 'smooth' });
        return;
    }

    // If all validations pass
    if (isValid) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch('/api/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // Optionally add JWT token here if needed for authentication
                    // 'Authorization': `Bearer ${jwt_token}`, 
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();
            if (response.ok) {
                messageElement.textContent = "Registration successful!";
                form.reset();

                // Show the success popup
                showSuccessPopup();
            } else {
                if (result.message.username) {
                    messageElement.textContent = result.message.username || "Registration failed.";
                }
                else if (result.message.email) {
                    messageElement.textContent = result.message.email || "Registration failed.";
                }
            }
        } catch (error) {
            messageElement.textContent = "Error occurred. Please try again later.";
        }
    }
});

function showError(fieldId, message) {
    const errorElement = document.getElementById(`${fieldId}_error`);
    const inputField = document.getElementById(fieldId);
    errorElement.textContent = message;
    inputField.classList.add('error');

    // Track the first invalid field to scroll into view
    if (!firstInvalidField) {
        firstInvalidField = inputField;
    }
}

// Function to show success popup
function showSuccessPopup() {
    const popup = document.getElementById('success-popup');
    popup.style.display = 'flex'; // Show the popup

    // Close the popup when the "Close" button is clicked
    document.getElementById('close-popup').addEventListener('click', () => {
        popup.style.display = 'none';
    });
}


// Real-time validation on input
document.querySelectorAll('input, select').forEach((element) => {
    element.addEventListener('input', () => {
        const fieldName = element.name;
        const form = document.forms['registration-form'];
        const errorMessage = validateField(element, form);

        const errorElement = document.getElementById(`${fieldName}_error`);
        if (errorMessage) {
            errorElement.textContent = errorMessage;
            element.classList.add('error');
        } else {
            errorElement.textContent = "";
            element.classList.remove('error');
        }
    });
});

function validateField(field, form) {
    switch (field.name) {
        case 'first_name':
        case 'last_name':
            if (field.value.length < 2) return "Name must be at least 2 characters.";
            if (field.value.length > 30) return "Name must not exceed 30 characters.";
            return "";
        case 'username':
            if (field.value.length < 4) return "Username must be at least 4 characters.";
            if (field.value.length > 20) return "Username must not exceed 20 characters.";
            return "";
        case 'email':
            const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            return !emailRegex.test(field.value) ? "Please enter a valid email address." : "";
        case 'password':
            const passwordRegex = /^(?=.*\d)(?=.*[a-zA-Z])(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
            return !passwordRegex.test(field.value) ? "Password must be at least 8 characters long, and include a number and special character." : "";
        case 'confirm_password':
            // Ensure confirm password matches password
            if (field.value !== form.password.value) {
                return "Passwords do not match.";
            }
            return "";
        case 'role':
            return !field.value ? "Please select a role." : "";
        case 'checkbox':
            return !field.checked ? "You must accept the Terms & Conditions." : "";
        default:
            return "";
    }
}
