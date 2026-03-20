import os
import json
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
django.setup()

from solutions.models import Solution, StrategyNode

def load_sample_solution():
    sample_data = {
        "metadata": {
            "name": "6-Max NL500 PS Ante (Sample)",
            "stack_depth": 100,
            "rake": 0.05,
            "ante": 0.1
        },
        "nodes": [
            { "hand": "AA", "actions": {"Raise": 0.85, "Call": 0.15}, "ev": 12.4, "equity": 0.88 },
            { "hand": "KK", "actions": {"Raise": 0.80, "Call": 0.20}, "ev": 10.2, "equity": 0.82 },
            { "hand": "QQ", "actions": {"Raise": 0.75, "Call": 0.25}, "ev": 8.5, "equity": 0.78 },
            { "hand": "AKs", "actions": {"Raise": 0.70, "Call": 0.30}, "ev": 7.2, "equity": 0.65 },
            { "hand": "72o", "actions": {"Fold": 1.0}, "ev": -0.8, "equity": 0.28 }
        ]
    }

    # Create the Solution
    sol, created = Solution.objects.update_or_create(
        name=sample_data["metadata"]["name"],
        defaults={
            "stack_depth": sample_data["metadata"]["stack_depth"],
            "rake": sample_data["metadata"]["rake"]
            # To support 'ante' in the future, we would add the field to the model
        }
    )

    if created:
        print(f"Created new solution: {sol.name}")
    else:
        print(f"Updating existing solution: {sol.name}")

    # Clear old nodes if any
    StrategyNode.objects.filter(solution=sol, path='root').delete()

    # Create new nodes
    for node in sample_data["nodes"]:
        StrategyNode.objects.create(
            solution=sol,
            path="root",
            hand=node["hand"],
            actions=node["actions"],
            ev=node.get("ev", 0),
            equity=node.get("equity", 0)
        )

    print(f"Successfully loaded {len(sample_data['nodes'])} strategy nodes.")

if __name__ == "__main__":
    load_sample_solution()
