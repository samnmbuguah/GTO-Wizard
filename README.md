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

### One-Step Deployment

Run the included deployment script to build, start services, and seed the database:

```bash
./deploy.sh
```

The application will be available at:
- **Frontend App**: [http://localhost:8089](http://localhost:8089)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Admin Panel**: [http://localhost:8000/admin/](http://localhost:8000/admin/)

### 🔐 Authentication & Security

Access is restricted. A demo profile is provided for exploring the solver workspace:
- **Username**: `player1`
- **Password**: `Player1_Poker2026!`

> [!IMPORTANT]
> **Production Security**: Passwords and keys are managed via `.env`. Never commit the `DATABASE_URL` or `SUPERUSER_PASSWORD` directly to the codebase. The `deploy.sh` script automatically reads from the host environment to populate these variables during build.

## 🎨 Professional UI Clone Highlights

- **3-Column Workspace**: Optimized for high-density poker data (18vw Sidebar / Center Matrix / Info Panel).
- **Horizontal Action Segments**: Strategy matrix cells use stacked horizontal gradients (Fold: Blue, Call: Green, Raise: Red) for immediate parity with industry standards.
- **Dynamic Filtering**: Left sidebar supports hierarchical navigation (SRP, 3-BET, 4-BET) and multi-stack depth filtering.
- **Enhanced Board Selector**: 1:1 color parity for suits and responsive card toggling.

## 🧪 Testing Coverage

The project maintains high stability with comprehensive test suites:

### Frontend (Vitest)
```bash
cd frontend
npm run test
```
Tests cover: Dashboard navigation, Board selection logic, and Strategy Matrix rendering.

### Backend (Django)
```bash
cd backend
source venv/bin/activate
python manage.py test
```
**Coverage**: 60+ tests (100% pass rate) covering API filters, Node Locking, Equity distributions, and Solver configurations.

## 📜 License
MIT License - Created for Professional Poker Development.
