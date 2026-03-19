import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
django.setup()

from django.contrib.auth.models import User
from solutions.models import Solution, StrategyNode

# Create superuser
su_pass = os.getenv('SUPERUSER_PASSWORD', 'fallback')
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', su_pass)
    print("Superuser created.")
else:
    u = User.objects.get(username='admin')
    u.set_password(su_pass)
    u.save()
    print("Superuser password updated.")

# Create normal user for public demo/README
nu_pass = os.getenv('NORMAL_USER_PASSWORD', 'fallback')
if not User.objects.filter(username='player1').exists():
    User.objects.create_user('player1', 'player1@example.com', nu_pass)
    print("Normal user created.")
else:
    u = User.objects.get(username='player1')
    u.set_password(nu_pass)
    u.save()
    print("Normal user password updated.")

# Create diverse textured solutions
textures = [
    ('High Board', 'High'),
    ('Low Board', 'Low'),
    ('Monotone Board', 'Monotone'),
    ('Paired Board', 'Paired'),
]

for name_suffix, texture in textures:
    sol, created = Solution.objects.get_or_create(
        name=f"6-Max Cash 100bb {name_suffix}",
        defaults={
            'rake': 0.05,
            'stack_depth': 100,
            'flop_texture': texture
        }
    )
    if created or not StrategyNode.objects.filter(solution=sol, path='root').exists():
        StrategyNode.objects.create(
            solution=sol,
            path='root',
            hand='AA',
            actions={'Fold': 0.1, 'Call': 0.3, 'Raise': 0.6} if texture == 'High' else {'Fold': 0.6, 'Call': 0.3, 'Raise': 0.1}
        )

print("Database seeded with textured solutions and strategy nodes.")

# Create a test solution
solution, created = Solution.objects.get_or_create(
    name="6-Max Cash 100bb Open SB",
    defaults={
        "rake": 0.05,
        "stack_depth": 100
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
