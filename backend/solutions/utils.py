import json
import zipfile
import io
from django.db import transaction
from .models import Solution, StrategyNode

def process_sif_upload(zip_file_obj):
    """
    Processes a ZIP file containing metadata.json and nodes.json.
    """
    with zipfile.ZipFile(zip_file_obj) as z:
        # 1. Parse Metadata
        try:
            with z.open('metadata.json') as f:
                metadata = json.load(f)
        except KeyError:
            raise ValueError("ZIP archive must contain metadata.json")

        # 2. Update or Create Solution
        name = metadata.get('name', 'Uploaded Solution')
        with transaction.atomic():
            solution, created = Solution.objects.update_or_create(
                name=name,
                defaults={
                    'game_type': metadata.get('game_type', '6-Max'),
                    'stack_depth': metadata.get('stack_depth', 100),
                    'rake': metadata.get('rake', 0.0),
                    'ante': metadata.get('ante', 0.0),
                    'flop_texture': metadata.get('flop_texture', 'Rainbow'),
                    'config': metadata # Store all metadata in the config field too
                }
            )

            # 3. Parse Nodes
            try:
                with z.open('nodes.json') as f:
                    nodes_data = json.load(f)
            except KeyError:
                raise ValueError("ZIP archive must contain nodes.json")

            # 4. Bulk Create Nodes
            # Clear existing if updating
            if not created:
                StrategyNode.objects.filter(solution=solution).delete()

            node_objects = []
            for item in nodes_data:
                node_objects.append(StrategyNode(
                    solution=solution,
                    path=item.get('path', 'root'),
                    hand=item.get('hand'),
                    actions=item.get('actions', {}),
                    ev=item.get('ev'),
                    equity=item.get('equity')
                ))
            
            StrategyNode.objects.bulk_create(node_objects, batch_size=5000)
            
            return solution, len(node_objects)
