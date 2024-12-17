document.getElementById('registration-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const form = e.target;
    const messageElement = document.getElementById('message');
    
    // Clear previous messages
    messageElement.textContent = "";
    
    // Clear all error messages and remove error class
    const errorFields = ['first_name', 'last_name', 'username', 'email', 'password', 'role', 'checkbox'];
    errorFields.forEach(field => {
        document.getElementById(`${field}_error`).textContent = "";
        document.getElementById(field).classList.remove('error');
    });

    let isValid = true;

    // Validate First Name
    const firstName = document.getElementById('first_name').value.trim();
    if (firstName.length < 2 || firstName.length > 50) {
        isValid = false;
        document.getElementById('first_name_error').textContent = "First Name must be between 2 and 50 characters.";
        document.getElementById('first_name').classList.add('error');
    } else {
        document.getElementById('first_name').classList.remove('error');
        document.getElementById('first_name_error').textContent = "";
    }

    // Validate Last Name
    const lastName = document.getElementById('last_name').value.trim();
    if (lastName.length < 2 || lastName.length > 50) {
        isValid = false;
        document.getElementById('last_name_error').textContent = "Last Name must be between 2 and 50 characters.";
        document.getElementById('last_name').classList.add('error');
    } else {
        document.getElementById('last_name').classList.remove('error');
        document.getElementById('last_name_error').textContent = "";
    }

    // Validate Username
    const username = form.username.value.trim();
    if (username.length < 4 || username.length > 20) {
        isValid = false;
        document.getElementById('username_error').textContent = "Username must be between 4 and 20 characters.";
        document.getElementById('username').classList.add('error');
    }

    // Validate Email Format
    const email = form.email.value.trim();
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(email)) {
        isValid = false;
        document.getElementById('email_error').textContent = "Please enter a valid email address.";
        document.getElementById('email').classList.add('error');
    }

    // Validate Password (min length of 8, must include number & special char)
    const password = form.password.value;
    const passwordRegex = /^(?=.*\d)(?=.*[a-zA-Z])(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
    if (!passwordRegex.test(password)) {
        isValid = false;
        document.getElementById('password_error').textContent = "Password must be at least 8 characters long and include a number and a special character.";
        document.getElementById('password').classList.add('error');
    }

    // Validate Terms & Conditions
    const checkbox = form.checkbox.checked;
    if (!checkbox) {
        isValid = false;
        document.getElementById('checkbox_error').textContent = "You must accept the Terms & Conditions.";
        document.getElementById('checkbox').classList.add('error');
    }

    // Validate Role Selection
    const role = form.role.value;
    if (!role) {
        isValid = false;
        document.getElementById('role_error').textContent = "Please select a role.";
        document.getElementById('role').classList.add('error');
    }

    if (!isValid) {
        return;
    }

    // If all fields are valid, proceed with form submission
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
            messageElement.textContent = "Registration successful!";
            form.reset();
        } else {
            messageElement.textContent = result.message || "Registration failed.";
        }
    } catch (error) {
        messageElement.textContent = "Error occurred. Please try again later.";
    }
});
