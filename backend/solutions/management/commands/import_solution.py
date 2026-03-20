import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from solutions.models import Solution, StrategyNode

class Command(BaseCommand):
    help = 'Import a pre-solved poker solution from a JSON file (SIF format)'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the JSON solution file')
        parser.add_argument('--clear', action='store_true', help='Clear existing nodes for this solution before importing')

    def handle(self, *args, **options):
        file_path = options['file_path']
        
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        with open(file_path, 'r') as f:
            data = json.load(f)

        metadata = data.get('metadata', {})
        name = metadata.get('name', 'Unknown Solution')
        game_type = metadata.get('game_type', '6-Max')
        stack_depth = metadata.get('stack_depth', 100)
        rake = metadata.get('rake', 0.0)
        ante = metadata.get('ante', 0.0)

        with transaction.atomic():
            sol, created = Solution.objects.update_or_create(
                name=name,
                defaults={
                    'game_type': game_type,
                    'stack_depth': stack_depth,
                    'rake': rake,
                    'ante': ante
                }
            )

            if options['clear']:
                self.stdout.write(f"Clearing existing nodes for {sol.name}...")
                StrategyNode.objects.filter(solution=sol).delete()

            nodes_data = data.get('nodes', [])
            self.stdout.write(f"Importing {len(nodes_data)} nodes for '{sol.name}'...")

            node_objects = []
            for item in nodes_data:
                node_objects.append(StrategyNode(
                    solution=sol,
                    path=item.get('path', 'root'),
                    hand=item.get('hand'),
                    actions=item.get('actions', {}),
                    ev=item.get('ev'),
                    equity=item.get('equity')
                ))

            # Bulk create for performance
            StrategyNode.objects.bulk_create(node_objects, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"Successfully imported '{sol.name}'"))
