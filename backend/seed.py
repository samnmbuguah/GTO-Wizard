import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
django.setup()

from django.contrib.auth.models import User
from solutions.models import Solution, StrategyNode

# Create superuser
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("Superuser created.")

# Create a test solution
solution, created = Solution.objects.get_or_create(
    name="6-Max Cash 100bb Open SB",
    defaults={
        "rake": 0.05,
        "stack_depth": 100,
        "description": "Standard 6-max cash game opening range from SB."
    }
)

if created:
    print("Test solution created.")
    # Create some test nodes
    hands = ['AA', 'KK', 'QQ', 'AKs', 'A5s', '72o']
    for hand in hands:
        StrategyNode.objects.create(
            solution=solution,
            path="root",
            hand=hand,
            actions={"raise": 0.8, "call": 0.2} if hand != '72o' else {"fold": 1.0},
            ev=10.5 if hand == 'AA' else -0.5,
            equity=0.85 if hand == 'AA' else 0.32
        )
    print("Test nodes created.")
