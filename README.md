# GTO Wizard - Professional Poker Solver Interface

A world-class, responsive GTO (Game Theory Optimal) poker solver interface built with Django and React.

## 🚀 Key Features

- **High-Performance Matrix**: 13x13 grid with real-time resizing and high-visibility poker-standard coloring.
- **Node Locking**: Lock specific hand strategies to simulate exploitative play.
- **Equity Distribution**: Professional area charts showing range equity vs. villains.
- **Fully Responsive**: Designed for desktop power users and mobile-on-the-go with a slide-out drawer.
- **Dark/Light Mode**: Seamlessly transition between themes with high-contrast legibility.
- **Solution Library**: Professional navigation through thousands of solver spots.

## 🛠 Tech Stack

- **Frontend**: React 19, TypeScript, Tailwind CSS 4, Vite 8, Lucide Icons, Recharts.
- **Backend**: Django 6, Django REST Framework, PostgreSQL.
- **Infrastructure**: Docker & Docker Compose.

## 📦 Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)

### One-Step Deployment

Run the included deployment script to build and start all services:

```bash
./deploy.sh
```

The application will be available at:
- **Frontend Terminal**: [http://213.199.50.129:8089](http://213.199.50.129:8089)
- **Backend API**: [http://213.199.50.129:8000](http://213.199.50.129:8000)
- **Admin Panel**: [http://213.199.50.129:8000/admin/](http://213.199.50.129:8000/admin/)

### 🔐 Authentication (Default Credentials)

Access to the terminal and solver data is restricted. Use the following unprivileged user credentials to log in and explore the app:

- **Username**: `player1`
- **Password**: `Player1_Poker2026!`

> [!IMPORTANT]
> This is a public demonstration account. Superuser access and solver configurations should be managed securely via local environment variables and will never be committed to the repository.

## 🧪 Testing

### Frontend
```bash
cd frontend
npm run test
```

### Backend
```bash
cd backend
./venv/bin/python manage.py test
```

## 📜 License
MIT License - Created for Professional Poker Development.
