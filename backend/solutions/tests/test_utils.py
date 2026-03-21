import io
import json
import zipfile
from django.test import TestCase
from solutions.models import Solution, StrategyNode
from solutions.utils import process_sif_upload


class ProcessSifInterfaceTests(TestCase):
    def setUp(self):
        # Create a valid in-memory zip file
        self.metadata = {
            "name": "Test SIF Utils Solution",
            "stack_depth": 100,
            "rake": 0.05,
            "game_type": "6max_cash",
            "ante": False
        }
        self.nodes = [
            {"path": "r", "hand": "AA", "strategies": {"FOLD": 0, "CALL": 0.5, "RAISE": 0.5}},
            {"path": "r:c", "hand": "KK", "strategies": {"FOLD": 0.1, "CALL": 0.9}}
        ]

    def _create_zip(self, metadata=None, nodes=None, omit_metadata=False, omit_nodes=False):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            if not omit_metadata:
                zip_file.writestr("metadata.json", json.dumps(metadata or self.metadata))
            if not omit_nodes:
                zip_file.writestr("nodes.json", json.dumps(nodes or self.nodes))
        zip_buffer.seek(0)
        return zip_buffer

    def test_process_sif_upload_success(self):
        zip_file = self._create_zip()
        solution, nodes_created = process_sif_upload(zip_file)
        
        self.assertEqual(solution.name, "Test SIF Utils Solution")
        self.assertEqual(solution.stack_depth, 100)
        self.assertEqual(nodes_created, 2)
        self.assertEqual(StrategyNode.objects.filter(solution=solution).count(), 2)
        
        # Test idempotency (should update existing rather than create new)
        zip_file = self._create_zip()
        solution_2, nodes_created_2 = process_sif_upload(zip_file)
        self.assertEqual(solution.id, solution_2.id)
        self.assertEqual(Solution.objects.count(), 1)
        self.assertEqual(nodes_created_2, 2)

    def test_process_sif_upload_missing_metadata(self):
        zip_file = self._create_zip(omit_metadata=True)
        with self.assertRaisesMessage(ValueError, "ZIP archive must contain metadata.json"):
            process_sif_upload(zip_file)

    def test_process_sif_upload_missing_nodes(self):
        zip_file = self._create_zip(omit_nodes=True)
        with self.assertRaisesMessage(ValueError, "ZIP archive must contain nodes.json"):
            process_sif_upload(zip_file)

    def test_process_sif_upload_invalid_zip(self):
        with self.assertRaises(zipfile.BadZipFile):
            process_sif_upload(io.BytesIO(b"not a zip file"))

    def test_process_sif_upload_invalid_json(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", "{ invalid json ]")
        zip_buffer.seek(0)
        with self.assertRaises(json.JSONDecodeError):
            process_sif_upload(zip_buffer)
