# GTO Wizard - Best Practices Guide

## Overview
This guide outlines the best practices implemented for the GTO Wizard application to ensure code quality, automated testing, and reliable deployments.

## Code Quality Tools

### ESLint & Prettier
- **ESLint**: Configured with TypeScript, React, and Prettier integration
- **Prettier**: Consistent code formatting with defined style rules
- **Pre-commit hooks**: Automatic formatting and linting on commit

### Configuration Files
- `.eslintrc.js` - ESLint configuration
- `.prettierrc` - Prettier formatting rules
- `.prettierignore` - Files to exclude from formatting

### Usage
```bash
# Check linting
npm run lint:check

# Fix linting issues
npm run lint

# Check formatting
npm run format:check

# Fix formatting
npm run format

# Type checking
npm run type-check
```

## Testing

### Frontend Tests
- **Vitest**: Fast unit testing framework
- **Testing Library**: Component testing utilities
- **Coverage**: Code coverage reporting

### Backend Tests
- **Django TestCase**: Built-in testing framework
- **Coverage**: Test coverage reporting

### Usage
```bash
# Frontend tests
npm run test
npm run test:coverage

# Backend tests
cd backend
python manage.py test
```

## Deployment

### Automated Deployment Script
The `deploy.sh` script provides:
- Pre-deployment checks
- Automated testing
- Health checks
- Error handling and logging
- Colored output for better visibility

### Usage
```bash
# Full deployment with tests
./deploy.sh

# Skip tests (for quick deployments)
./deploy.sh --skip-tests

# Show help
./deploy.sh --help
```

### Docker Compose Features
- **Health checks**: Automatic service health monitoring
- **Multi-stage builds**: Development and production targets
- **Environment variables**: Flexible configuration
- **Restart policies**: Automatic recovery from failures

## CI/CD Pipeline

### GitHub Actions Workflow
The `.github/workflows/ci-cd.yml` includes:
- **Frontend testing**: Type checking, linting, formatting, unit tests
- **Backend testing**: Linting, database migrations, unit tests
- **Security scanning**: Vulnerability detection with Trivy
- **Automated deployment**: Conditional deployment on main branch
- **Notifications**: Success/failure notifications

### Pipeline Triggers
- Push to `main`/`master` branches
- Pull requests to `main`/`master` branches

## Development Workflow

### 1. Setup Development Environment
```bash
# Copy environment file
cp .env.example .env

# Install frontend dependencies
cd frontend
npm install --legacy-peer-deps

# Setup pre-commit hooks
npm run prepare

# Install backend dependencies
cd ../backend
pip install -r requirements.txt
```

### 2. Development Process
```bash
# Start development environment
./deploy.sh

# Make changes...

# Pre-commit hooks will automatically:
# - Run ESLint and fix issues
# - Format code with Prettier
# - Run tests (if configured)
```

### 3. Commit and Deploy
```bash
# Commit changes (pre-commit hooks run automatically)
git add .
git commit -m "feat: add new feature"

# Deploy changes
./deploy.sh
```

## Environment Configuration

### Development
- API URL: `http://localhost:8000/api`
- Frontend: `http://localhost:8089`
- Database: `localhost:5432`

### Production
- Configure `.env` with production values
- Set `BUILD_TARGET=production`
- Update `VITE_API_URL` to production backend URL

## Best Practices

### Code Quality
1. **Always run tests before committing**
2. **Follow TypeScript strict mode guidelines**
3. **Use meaningful variable and function names**
4. **Write tests for new features**
5. **Keep components small and focused**

### Security
1. **Never commit secrets or API keys**
2. **Use environment variables for configuration**
3. **Regularly update dependencies**
4. **Run security scans before deployment**

### Performance
1. **Optimize images and assets**
2. **Use code splitting for large applications**
3. **Monitor bundle size**
4. **Implement lazy loading where appropriate**

### Deployment
1. **Always test in development first**
2. **Use semantic versioning**
3. **Monitor deployment health**
4. **Rollback plan for failed deployments**

## Monitoring and Health Checks

### Health Check Endpoints
- Frontend: `http://localhost:8089`
- Backend API: `http://localhost:8000/api/`
- Database: PostgreSQL health check

### Logs and Monitoring
- Docker container logs: `docker compose logs [service]`
- Application logs: Check individual service logs
- Health check status: `docker compose ps`

## Troubleshooting

### Common Issues
1. **Port conflicts**: Check if ports are already in use
2. **Database connection**: Verify database is healthy
3. **Build failures**: Check logs and ensure dependencies are installed
4. **Permission issues**: Ensure Docker has proper permissions

### Debug Commands
```bash
# Check container status
docker compose ps

# View logs
docker compose logs [service-name]

# Restart services
docker compose restart [service-name]

# Clean up
docker compose down --volumes --remove-orphans
```

## Contributing

1. **Follow the code style guidelines**
2. **Write tests for new features**
3. **Update documentation**
4. **Use descriptive commit messages**
5. **Create pull requests for review**

## Support

For issues or questions:
1. Check this documentation
2. Review logs and error messages
3. Check GitHub Issues
4. Contact the development team
