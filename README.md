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
- **Frontend**: http://localhost:8089
- **Backend API**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin/ (User: `admin`, Pass: `admin123`)

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
