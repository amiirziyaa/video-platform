# Video Subscription Platform

This project is a complete backend and API for a video subscription service, built with Django and Django REST Framework. It includes a simple frontend powered by Django templates for user interaction.

## Features

- **User Management:** Secure user registration, login, and profile editing. Authentication is handled by JWT (JSON Web Tokens).
- **Content Structure:** Supports both standalone **Movies** and **Series** with seasons and episodes.
- **Subscription System:**
  - Multiple subscription plans with different access levels.
  - Full subscription lifecycle: Buy, Upgrade, Renew, and Cancel.
- **Payment Integration:**
  - Integrated with the Zarinpal payment gateway (in sandbox mode).
  - Full history of all successful payments.
- **User Interaction:**
  - **Watch History:** Tracks videos users have watched.
  - **Bookmarking:** Allows users to save videos to watch later.
  - **Commenting & Rating:** Users can leave comments and ratings on videos.
- **API First Design:** A comprehensive RESTful API for all major functionalities.
- **Django Template Frontend:** A simple, server-rendered frontend for browsing content and managing user accounts.

## Tech Stack

- **Backend:** Python, Django
- **API:** Django REST Framework
- **Authentication:** Simple JWT
- **Database:** SQLite3 (for development)

## Local Setup and Installation

Follow these steps to get the project running on your local machine.

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd video-platform
```

### 2. Create and Activate Virtual Environment
```bash
# For Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# For Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a file named `.env` in the project root and add your secret keys. You can use the `.env.example` as a template.
```ini
# in .env file
SECRET_KEY='your-django-secret-key-here'
ZARINPAL_MERCHANT_ID='your-zarinpal-test-uuid-here'
```
You will also need to update `config/settings.py` to read these variables (using a library like `python-decouple`).

### 5. Run Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create a Superuser
This will allow you to access the Django admin panel to manage content.
```bash
python manage.py createsuperuser
```

### 7. Run the Development Server
```bash
python manage.py runserver
```
The project will be available at `http://127.0.0.1:8000/`. The admin panel is at `http://127.0.0.1:8000/admin/`.

## API Endpoints

The API is accessible under the `/api/` prefix.

| Endpoint              | Methods      | Description                               |
| --------------------- | ------------ | ----------------------------------------- |
| `/api/users/`         | `POST`       | Register a new user.                      |
| `/api/token/`         | `POST`       | Obtain JWT access and refresh tokens.     |
| `/api/series/`        | `GET`        | List all series.                          |
| `/api/series/{slug}/` | `GET`        | Retrieve a series with all its episodes.  |
| `/api/videos/`        | `GET`, `POST`| List all videos/episodes or create a new one. |
| `/api/videos/{slug}/` | `GET`, `PUT`, `DELETE` | Retrieve, update, or delete a video.      |
| `/api/subscriptions/` | `GET`, `POST`| List your subscriptions or create a new one.|
| `/api/bookmarks/`     | `GET`, `POST`, `DELETE`| Manage your bookmarks.                    |
| `/api/comments/`      | `GET`, `POST`, `DELETE`| Manage your comments.                     |

## ER Diagram

```mermaid
erDiagram
    User {
        int id PK
        string username
        string email
        string phone_number
    }

    SubscriptionPlan {
        int id PK
        string name
        decimal price
        int duration_days
        int level
    }

    Subscription {
        int id PK
        int user_id FK
        int plan_id FK
        datetime start_date
        datetime end_date
        string status
    }

    Payment {
        int id PK
        int user_id FK
        int plan_id FK
        int subscription_id FK
        decimal amount
        string status
    }

    Series {
        int id PK
        string title
        string slug
        string description
        int release_year
    }

    Video {
        int id PK
        int series_id FK "nullable"
        int category_id FK "nullable"
        string title
        int season_number "nullable"
        int episode_number "nullable"
    }

    VideoCategory {
        int id PK
        string name
    }

    WatchHistory {
        int id PK
        int user_id FK
        int video_id FK
        datetime watched_at
        int rating "nullable"
    }

    VideoComment {
        int id PK
        int user_id FK
        int video_id FK
        string comment
    }

    VideoBookmark {
        int id PK
        int user_id FK
        int video_id FK
    }

    User ||--o{ Subscription : "has"
    User ||--o{ Payment : "makes"
    User ||--o{ WatchHistory : "has"
    User ||--o{ VideoComment : "writes"
    User ||--o{ VideoBookmark : "creates"

    SubscriptionPlan ||--o{ Subscription : "is of"
    SubscriptionPlan ||--o{ Payment : "is for"

    Subscription }o--|| Payment : "is paid by"

    Series ||--o{ Video : "contains episodes"

    VideoCategory ||--o{ Video : "categorizes"

    Video ||--o{ WatchHistory : "is watched in"
    Video ||--o{ VideoComment : "has"
    Video ||--o{ VideoBookmark : "is bookmarked in"