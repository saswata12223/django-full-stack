# Full Stack Expense Tracker

A beginner-friendly full stack expense and income tracker built with Django, SQLite, and Bootstrap 5. 
This project allows users to register, log in, and manage their personal finances securely.

## Features
- **User Authentication:** Built-in Django authentication for user registration, login, and secure sessions.
- **Dashboard:** At-a-glance summary of total income, expenses, current balance, and recent transactions.
- **Income & Expense Management:** Full CRUD (Create, Read, Update, Delete) functionality for both incomes and expenses.
- **Filtering & Search:** Easily search for descriptions or filter records by date and categories.
- **Responsive Design:** Clean UI using Bootstrap 5 that works nicely on both desktop and mobile screens.

## Requirements
- Python 3.8+
- Django 4.2+
- SQLite (comes pre-installed with Python)

## Installation & Setup Instructions

Follow these steps in your terminal (Command Prompt or PowerShell on Windows, or Terminal on macOS/Linux) to set up and run the project locally.

### 1. Create a Virtual Environment
Create an isolated Python environment to keep project dependencies separate:
```bash
python -m venv venv
```

### 2. Activate the Virtual Environment
**On Windows:**
```bash
venv\Scripts\activate
```
**On macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies
Install Django and any other requirements from `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Run Migrations
Set up the SQLite database and create the necessary tables for models and authentication:
```bash
python manage.py migrate
```

### 5. Create a Superuser (Optional but Recommended)
Create an admin user to access the Django admin panel:
```bash
python manage.py createsuperuser
```
Follow the prompts to enter a username, email (optional), and password.

### 6. Start the Server
Run the local development server:
```bash
python manage.py runserver
```

### 7. Access the Application
Open your web browser and navigate to the default URL:
http://127.0.0.1:8000/

To access the admin panel, go to:
http://127.0.0.1:8000/admin/

## Important Notes
- **Security:** CSRF tokens are implemented on all forms. Ensure you are logged in to access dashboard functionality.
- **Data Privacy:** Expenses and incomes are tied strictly to the logged-in user. You cannot see other users' financial data.
- **Customization:** Feel free to extend category choices in `models.py` or modify the Bootstrap template files located in `expenses/templates/expenses/`.
