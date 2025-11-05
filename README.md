# CSCI314-Project

---
**Project Overview**

This is project focuses and the design and development of a system to match Corporate Social Responsibility
(CSR) corporate volunteers (CV) to the person-in-need (PIN). Each company will have a main CSR
Representative (on behalf of the CVs) to connect with the PIN.

---
**Group Information**

Module: CSCI314

Tutorial Group: T06

Group Name: Monday Blues

---

**Project Features**

The system provides the below listed features.

  **User Registrations, Login system & Admin Authentication**

   * Users can register as their desired role(Platform Manager, CSR, Volunteer, PIN)
   * Users can login into the system to manage their profiles or perform required actions
   * Admin can authenticate the user accounts are valid, and manage the accounts accordingly(suspension, deletion etc.)

  **Category Management**

   * Platform Manager can add categories as required
   * Platform Manager can remove outdated categories as required

  **View Request Listing**
   * Users can view a list of requests put up by PIN
   * Users can click on more details for specific requests

  **PIN Request Creation & Review**
   * PINs can create a request and fill in the necessary details
   * PINs can review completed requests as they need

  **CSR Request management & Volunteer assigning**
   * CSRs viewing the specific request can accept or shortlist it
   * CSRs can assign their desired Volunteer after accepting the request

  **Volunteer Request management**
   * Volunteer can view the assigned request
   * Volunteer can choose to accept or decline assigned requests
   * Volunteer can mark tasks as completed

---
**Technologies used**

* Frontend: HTML & CSS
* Backend: Python Flask & sqlite
* Version Control: Git and Github for code management and collaboration

---
**Set up Instructions**
The below instructions are on how to set up the system locally

1. Clone the Git Repository
``````
git clone https://github.com/<your-username>/<repo-name>.git
``````
``````
- Step 1: Make sure venv is installed
  sudo apt install python3-venv -y

- Step 2: Create a virtual environment (in your project folder)
  python3 -m venv venv

- Step 3: Activate the virtual environment
  source venv/bin/activate

- Step 4: Now install Flask safely
  pip install flask
``````

last step. Run the program in your preferred IDE
Open a browser and enter "http://127.0.0.1:5000/" for the login page
