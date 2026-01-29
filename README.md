Queue Management System

A web-based queue management system built using Flask. This application allows customers to take tickets, staff to serve customers at desks, and administrators to manage users, desks, advertisements, and system settings. The system automatically assigns waiting customers to available desks and resets tickets daily.

Features

Customer ticket generation and queueing.

Automatic assignment of customers to free desks.

Staff dashboard for serving and finishing customers.

Admin panel for managing users, desks, and system information.

Daily automatic ticket reset.

Real-time queue and desk status updates.

Advertisement upload and activation.

Analytics for served customers and waiting times.

Project Structure
project/
│── app.py
│── database.db
│── templates/
│   ├── admin.html
│   ├── staff.html
│   ├── customer.html
│   └── now_serving.html
│── static/
│   ├── ads/
│   └── assets/

Installation

Clone this repository:

git clone https://github.com/your-username/queue-management-system.git
cd queue-management-system


Make sure you have Python 3.8+ installed.

Install dependencies:

pip install flask werkzeug

Usage

Run the application:

python app.py


Open in a browser:

http://127.0.0.1:5000

Default user credentials:
Username: admin
Password: admin123

How to Use

Customers open the home page and take a ticket.
Staff log in and serve customers from assigned desks.
Staff click Finish to complete service and call the next customer.
Admins manage users, desks, ads, and system information.
The system resets tickets automatically each day.

Screenshots
<img width="1895" height="935" alt="image" src="https://github.com/user-attachments/assets/fd4dbad1-5710-4d96-bb8e-dfd2c10b5ad7" />
<img width="1893" height="937" alt="image" src="https://github.com/user-attachments/assets/645dfda5-7609-426b-a42e-58d71211f479" />
<img width="1616" height="840" alt="image" src="https://github.com/user-attachments/assets/5aba0f4e-c955-49eb-8248-66afb5d946df" />
<img width="1910" height="910" alt="image" src="https://github.com/user-attachments/assets/1018fd73-3a21-4a88-9e87-f002391c0d01" />


Author
- Innocent Malya (donmalya-tech)
