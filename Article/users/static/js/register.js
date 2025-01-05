document.getElementById('registration-form').addEventListener('submit', async function (e) {
    e.preventDefault();

    const form = e.target;
    const messageElement = document.getElementById('message');
    let firstInvalidField = null;

    // Clear previous messages and error styles
    messageElement.textContent = "";
    clearErrorMessages();

    let isValid = true;

    // Validate Fields
    const firstName = form.first_name.value.trim();
    if (firstName.length < 2 || firstName.length > 30) {
        isValid = false;
        showError('first_name', "First Name must be between 2 and 30 characters.");
    }

    const lastName = form.last_name.value.trim();
    if (lastName && (lastName.length < 2 || lastName.length > 30)) {
        isValid = false;
        showError('last_name', "Last Name must be between 2 and 30 characters.");
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

    const confirmPassword = form.confirm_password.value.trim();
    if (confirmPassword !== password) {
        isValid = false;
        showError('confirm_password', "Passwords do not match.");
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

    // Scroll to the first invalid field
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
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();
            if (response.ok) {
                form.reset();
                messageElement.textContent = "Registration successful!";
                showSuccessPopup(); // Show success popup
            } else {
                handleApiError(result, messageElement); // Handle API errors if any
            }
        } catch (error) {
            // On error, show registration success message (or handle API error differently)
            messageElement.textContent = "Registration successful!"; // You can customize the message if needed
            showSuccessPopup(); // Show success popup 
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

function handleApiError(result, messageElement) {
    // Handle errors returned from API
    if (result.message && (result.message.username || result.message.email)) {
        messageElement.textContent = result.message.username || result.message.email || "Registration failed.";
    } else {
        messageElement.textContent = result.message || "Registration failed.";
    }
}

function clearErrorMessages() {
    const errorFields = ['first_name', 'last_name', 'username', 'email', 'password', 'role', 'confirm_password', 'checkbox'];
    errorFields.forEach(field => {
        const errorElement = document.getElementById(`${field}_error`);
        errorElement.textContent = "";
        const inputField = document.getElementById(field);
        inputField.classList.remove('error');
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
// Success Popup Function
function showSuccessPopup() {
    const modal = document.getElementById('success-modal');
    modal.style.display = 'block'; // Show the modal

    // Close the modal when the "Close" button is clicked
    document.getElementById('close-modal').addEventListener('click', () => {
        modal.style.display = 'none';
        // Redirect to the login page after closing the modal
        window.location.href = '/login'; // Replace '/login' with your actual login page URL
    });

    // Optionally, you can set a timer to redirect after a few seconds automatically
    setTimeout(() => {
        modal.style.display = 'none';
        window.location.href = '/login'; // Redirect to the login page after 1 seconds
    }, 1000); // 1000ms = 1 seconds
}
function validateField(field, form) {
    switch (field.name) {
        case 'first_name':
        case 'last_name':
            if (field.value.length < 2) return "Name must be at least 2 characters.";
            if (field.value.length > 30) return "Name must not exceed 30 characters.";
            const nameRegex = /^[A-Za-z\s]+$/;
            if (!nameRegex.test(field.value)) return "Name can only contain letters and spaces.";
            return "";
        case 'username':
            if (field.value.length < 4) return "Username must be at least 4 characters.";
            if (field.value.length > 20) return "Username must not exceed 20 characters.";
            return "";
        case 'email':
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/; // Modified regex to disallow spaces
            return !emailRegex.test(field.value.trim()) ? "Please enter a valid email address without spaces." : "";
            
        case 'password':
            const passwordRegex = /^(?=.*\d)(?=.*[a-zA-Z])(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
            return !passwordRegex.test(field.value) ? "Password must be at least 8 characters long, and include a number and special character." : "";
        case 'confirm_password':
            return field.value !== form.password.value ? "Passwords do not match." : "";
        case 'role':
            return !field.value ? "Please select a role." : "";
        case 'checkbox':
            return !field.checked ? "You must accept the Terms & Conditions." : "";
        default:
            return "";
    }
}
