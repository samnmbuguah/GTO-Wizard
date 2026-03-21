from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
import json
import io
import zipfile
from solutions.models import Solution, StrategyNode, SolverConfig


class SolutionAPITests(APITestCase):
    """Tests for the Solution list/detail and filtering endpoints."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', email='a@b.com', password='password123'
        )
        self.client.login(username='admin', password='password123')

        # Create diverse solutions mimicking the left panel's data
        self.sol_sb_100 = Solution.objects.create(
            name="SB vs BB 3BET", rake=0.05, stack_depth=100, flop_texture='High'
        )
        self.sol_btn_100 = Solution.objects.create(
            name="BTN vs BB SRP", rake=0.05, stack_depth=100, flop_texture='Low'
        )
        self.sol_co_100 = Solution.objects.create(
            name="CO vs BB SRP", rake=0.05, stack_depth=100, flop_texture='Rainbow'
        )
        self.sol_sb_150 = Solution.objects.create(
            name="SB vs BB SRP 150bb", rake=0.05, stack_depth=150, flop_texture='Paired'
        )
        self.sol_utg_100 = Solution.objects.create(
            name="UTG vs BB 4BET", rake=0.0, stack_depth=100, flop_texture='Monotone'
        )
        self.sol_mp_150 = Solution.objects.create(
            name="MP vs BTN SRP", rake=0.03, stack_depth=150, flop_texture='Straight-Friendly'
        )

    # ── Basic CRUD ──────────────────────────────────────────────

    def test_get_solutions_list(self):
        url = reverse('solution-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 6)

    def test_get_solution_detail(self):
        url = reverse('solution-detail', args=[self.sol_sb_100.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'SB vs BB 3BET')
        self.assertEqual(response.data['stack_depth'], 100)

    def test_create_solution(self):
        url = reverse('solution-list')
        data = {
            'name': 'New Test Solution',
            'rake': 0.04,
            'stack_depth': 200,
            'flop_texture': 'High',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Solution.objects.count(), 7)
        self.assertEqual(response.data['name'], 'New Test Solution')

    def test_update_solution(self):
        url = reverse('solution-detail', args=[self.sol_sb_100.id])
        data = {'name': 'SB vs BB 3BET Updated', 'rake': 0.06, 'stack_depth': 100, 'flop_texture': 'High'}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sol_sb_100.refresh_from_db()
        self.assertEqual(self.sol_sb_100.name, 'SB vs BB 3BET Updated')

    def test_delete_solution(self):
        url = reverse('solution-detail', args=[self.sol_mp_150.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Solution.objects.count(), 5)

    # ── Single Filter: name (position matching) ─────────────────

    def test_filter_by_name_sb(self):
        """Clicking 'SB vs BB' sends ?name=SB — should match solutions containing 'SB'."""
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'SB'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [s['name'] for s in response.data]
        self.assertEqual(len(names), 2)  # SB vs BB 3BET + SB vs BB SRP 150bb
        for name in names:
            self.assertIn('SB', name)

    def test_filter_by_name_btn(self):
        """Clicking 'BTN vs BB' sends ?name=BTN."""
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'BTN'})
        names = [s['name'] for s in response.data]
        self.assertEqual(len(names), 2)  # BTN vs BB SRP + MP vs BTN SRP
        for name in names:
            self.assertIn('BTN', name)

    def test_filter_by_name_co(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'CO'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'CO vs BB SRP')

    def test_filter_by_name_utg(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'UTG'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'UTG vs BB 4BET')

    def test_filter_by_name_mp(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'MP'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'MP vs BTN SRP')

    def test_filter_by_name_case_insensitive(self):
        """name filter uses icontains — should be case-insensitive."""
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'sb'})
        self.assertEqual(len(response.data), 2)

    def test_filter_by_name_no_match(self):
        """A position with no solutions should return an empty list."""
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'HJ'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # ── Single Filter: stack_depth ──────────────────────────────

    def test_filter_by_stack_depth_100(self):
        """Clicking the '100' stack button sends ?stack_depth=100."""
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 100})
        self.assertEqual(len(response.data), 4)  # SB, BTN, CO, UTG at 100bb
        for s in response.data:
            self.assertEqual(s['stack_depth'], 100)

    def test_filter_by_stack_depth_150(self):
        """Clicking the '150' stack button sends ?stack_depth=150."""
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 150})
        self.assertEqual(len(response.data), 2)  # SB 150bb + MP 150bb
        for s in response.data:
            self.assertEqual(s['stack_depth'], 150)

    def test_filter_by_stack_depth_no_match(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 200})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # ── Single Filter: rake ─────────────────────────────────────

    def test_filter_by_rake(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'rake': 0.05})
        self.assertEqual(len(response.data), 4)

    def test_filter_by_rake_zero(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'rake': 0.0})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'UTG vs BB 4BET')

    # ── Combined Filters (simulating left panel interactions) ───

    def test_filter_stack_depth_and_name_sb_100(self):
        """Left panel: Stack=100, Position=SB vs BB → ?stack_depth=100&name=SB"""
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 100, 'name': 'SB'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'SB vs BB 3BET')

    def test_filter_stack_depth_and_name_sb_150(self):
        """Left panel: Stack=150, Position=SB vs BB → ?stack_depth=150&name=SB"""
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 150, 'name': 'SB'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'SB vs BB SRP 150bb')

    def test_filter_stack_depth_and_name_btn_100(self):
        """Left panel: Stack=100, Position=BTN vs BB"""
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 100, 'name': 'BTN'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'BTN vs BB SRP')

    def test_filter_stack_depth_and_name_no_match(self):
        """Combining filters that match nothing should return empty list."""
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 100, 'name': 'MP'})
        # MP vs BTN SRP is at stack_depth=150, not 100
        self.assertEqual(len(response.data), 0)

    def test_filter_all_three_params(self):
        """Combining all query params: ?rake=0.05&stack_depth=100&name=SB"""
        url = reverse('solution-list')
        response = self.client.get(url, {'rake': 0.05, 'stack_depth': 100, 'name': 'SB'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'SB vs BB 3BET')

    def test_filter_all_three_params_mismatch(self):
        """UTG has rake=0.0, so filtering with rake=0.05 returns nothing."""
        url = reverse('solution-list')
        response = self.client.get(url, {'rake': 0.05, 'stack_depth': 100, 'name': 'UTG'})
        self.assertEqual(len(response.data), 0)

    # ── Tab simulation (3BET, 4BET, SRP, HU via name) ──────────

    def test_filter_by_tab_3bet(self):
        """Tab='3 BET' should match solutions with '3BET' in name."""
        url = reverse('solution-list')
        response = self.client.get(url, {'name': '3BET'})
        self.assertEqual(len(response.data), 1)
        self.assertIn('3BET', response.data[0]['name'])

    def test_filter_by_tab_4bet(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'name': '4BET'})
        self.assertEqual(len(response.data), 1)
        self.assertIn('4BET', response.data[0]['name'])

    def test_filter_by_tab_srp(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'name': 'SRP'})
        self.assertEqual(len(response.data), 4)
        for s in response.data:
            self.assertIn('SRP', s['name'])

    # ── Response shape validation ───────────────────────────────

    def test_solution_response_contains_expected_fields(self):
        url = reverse('solution-detail', args=[self.sol_sb_100.id])
        response = self.client.get(url)
        expected_fields = ['id', 'name', 'rake', 'stack_depth', 'flop_texture', 'created_at']
        for field in expected_fields:
            self.assertIn(field, response.data, f"Field '{field}' missing from response")

    def test_solution_list_response_is_list(self):
        url = reverse('solution-list')
        response = self.client.get(url)
        self.assertIsInstance(response.data, list)

    # ── Non-existent solution ───────────────────────────────────

    def test_get_nonexistent_solution_returns_404(self):
        url = reverse('solution-detail', args=[9999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── Upload SIF Endpoint ─────────────────────────────────────

    def _create_mock_zip(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("metadata.json", json.dumps({
                "name": "API Test Solution",
                "stack_depth": 50,
                "rake": 0.05,
                "game_type": "6max_cash",
                "ante": False
            }))
            zip_file.writestr("nodes.json", json.dumps([
                {"path": "r", "hand": "AA", "strategies": {"FOLD": 0.2, "CALL": 0.8}}
            ]))
        zip_buffer.seek(0)
        return zip_buffer

    def test_upload_solution_success(self):
        zip_buffer = self._create_mock_zip()
        uploaded_file = SimpleUploadedFile(
            "test_solution.zip", 
            zip_buffer.read(), 
            content_type="application/zip"
        )
        
        response = self.client.post(reverse('solution-upload'), {'file': uploaded_file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Successfully imported solution')
        self.assertEqual(response.data['node_count'], 1)
        self.assertTrue(Solution.objects.filter(name="API Test Solution").exists())

    def test_upload_solution_no_file(self):
        response = self.client.post(reverse('solution-upload'), {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'No file uploaded')

    def test_upload_solution_invalid_file(self):
        uploaded_file = SimpleUploadedFile(
            "bad.txt", 
            b"not a zip file", 
            content_type="text/plain"
        )
        response = self.client.post(reverse('solution-upload'), {'file': uploaded_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file is not a zip file', response.data['error'].lower())

class SolutionUnauthenticatedTests(APITestCase):
    """Test that unauthenticated users can read but not write solutions."""

    def setUp(self):
        self.sol = Solution.objects.create(
            name="Public Solution", rake=0.05, stack_depth=100
        )

    def test_unauthenticated_can_list_solutions(self):
        url = reverse('solution-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_unauthenticated_can_read_solution_detail(self):
        url = reverse('solution-detail', args=[self.sol.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_can_filter_solutions(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 100, 'name': 'Public'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_unauthenticated_cannot_create_solution(self):
        url = reverse('solution-list')
        data = {'name': 'Hack', 'rake': 0.0, 'stack_depth': 100, 'flop_texture': 'High'}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_unauthenticated_cannot_delete_solution(self):
        url = reverse('solution-detail', args=[self.sol.id])
        response = self.client.delete(url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.assertEqual(Solution.objects.count(), 1)  # Not deleted


class StrategyNodeFilteringTests(APITestCase):
    """Test StrategyNode filtering by solution_id and path."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', email='a@b.com', password='password123'
        )
        self.client.login(username='admin', password='password123')

        self.sol1 = Solution.objects.create(name="Sol A", rake=0.05, stack_depth=100)
        self.sol2 = Solution.objects.create(name="Sol B", rake=0.05, stack_depth=150)

        # Create nodes for sol1
        self.node_aa = StrategyNode.objects.create(
            solution=self.sol1, path='root', hand='AA',
            actions={'Raise': 1.0, 'Call': 0.0, 'Fold': 0.0}, ev=15.2, equity=0.85
        )
        self.node_kk = StrategyNode.objects.create(
            solution=self.sol1, path='root', hand='KK',
            actions={'Raise': 0.9, 'Call': 0.1, 'Fold': 0.0}, ev=12.1, equity=0.82
        )
        self.node_aa_flop = StrategyNode.objects.create(
            solution=self.sol1, path='root/check/bet50', hand='AA',
            actions={'Raise': 0.0, 'Call': 0.8, 'Fold': 0.2}, ev=8.5, equity=0.78
        )

        # Create nodes for sol2
        self.node_aks = StrategyNode.objects.create(
            solution=self.sol2, path='root', hand='AKs',
            actions={'Raise': 0.7, 'Call': 0.3, 'Fold': 0.0}, ev=10.0, equity=0.65
        )

    def test_get_all_nodes(self):
        url = reverse('strategynode-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

    def test_filter_nodes_by_solution_id(self):
        """When user selects a solution, frontend fetches nodes by solution_id."""
        url = reverse('strategynode-list')
        response = self.client.get(url, {'solution_id': self.sol1.id})
        self.assertEqual(len(response.data), 3)
        for node in response.data:
            self.assertEqual(node['solution'], self.sol1.id)

    def test_filter_nodes_by_solution_id_other(self):
        url = reverse('strategynode-list')
        response = self.client.get(url, {'solution_id': self.sol2.id})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['hand'], 'AKs')

    def test_filter_nodes_by_path_root(self):
        """Frontend requests path='root' to get the preflop matrix."""
        url = reverse('strategynode-list')
        response = self.client.get(url, {'path': 'root'})
        self.assertEqual(len(response.data), 3)  # AA, KK from sol1, AKs from sol2
        for node in response.data:
            self.assertEqual(node['path'], 'root')

    def test_filter_nodes_by_solution_and_path(self):
        """Combined: solution_id + path='root' → only root nodes for that solution."""
        url = reverse('strategynode-list')
        response = self.client.get(url, {'solution_id': self.sol1.id, 'path': 'root'})
        self.assertEqual(len(response.data), 2)
        hands = [n['hand'] for n in response.data]
        self.assertIn('AA', hands)
        self.assertIn('KK', hands)

    def test_filter_nodes_by_deep_path(self):
        """Navigating into the tree: path='root/check/bet50'."""
        url = reverse('strategynode-list')
        response = self.client.get(url, {'path': 'root/check/bet50'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['hand'], 'AA')

    def test_node_response_contains_strategy_data(self):
        """Verify node responses include actions, ev, and equity for the right panel."""
        url = reverse('strategynode-detail', args=[self.node_aa.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('actions', response.data)
        self.assertIn('ev', response.data)
        self.assertIn('equity', response.data)
        self.assertEqual(response.data['actions']['Raise'], 1.0)
        self.assertAlmostEqual(response.data['ev'], 15.2)

    def test_filter_nodes_empty_results(self):
        url = reverse('strategynode-list')
        response = self.client.get(url, {'solution_id': 9999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class AggregateReportTests(APITestCase):
    """Test the aggregate report endpoint used by ReportsView."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', email='a@b.com', password='password123'
        )
        self.client.login(username='admin', password='password123')

        # Create solutions with various textures
        self.sol_high = Solution.objects.create(name="High Board", flop_texture='High')
        self.sol_low = Solution.objects.create(name="Low Board", flop_texture='Low')
        self.sol_paired = Solution.objects.create(name="Paired Board", flop_texture='Paired')

        # Add root nodes with action frequencies
        StrategyNode.objects.create(
            solution=self.sol_high, path='root', hand='AA',
            actions={'Fold': 0.0, 'Call': 0.3, 'Raise': 0.7}
        )
        StrategyNode.objects.create(
            solution=self.sol_high, path='root', hand='KK',
            actions={'Fold': 0.1, 'Call': 0.4, 'Raise': 0.5}
        )
        StrategyNode.objects.create(
            solution=self.sol_low, path='root', hand='72o',
            actions={'Fold': 0.8, 'Call': 0.1, 'Raise': 0.1}
        )

    def test_aggregate_report_returns_data(self):
        url = reverse('aggregate-report')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        # Should have entries for High and Low (Paired has no nodes)
        textures = [r['texture'] for r in response.data]
        self.assertIn('High', textures)
        self.assertIn('Low', textures)
        self.assertNotIn('Paired', textures)

    def test_aggregate_report_averages(self):
        url = reverse('aggregate-report')
        response = self.client.get(url)
        high_report = next(r for r in response.data if r['texture'] == 'High')
        # Average of 2 nodes: (0.0+0.1)/2=0.05, (0.3+0.4)/2=0.35, (0.7+0.5)/2=0.6
        self.assertAlmostEqual(high_report['avg_fold'], 0.05)
        self.assertAlmostEqual(high_report['avg_call'], 0.35)
        self.assertAlmostEqual(high_report['avg_raise'], 0.6)
        self.assertEqual(high_report['sample_size'], 2)

    def test_aggregate_report_single_node(self):
        url = reverse('aggregate-report')
        response = self.client.get(url)
        low_report = next(r for r in response.data if r['texture'] == 'Low')
        self.assertAlmostEqual(low_report['avg_fold'], 0.8)
        self.assertEqual(low_report['sample_size'], 1)

    def test_aggregate_report_empty_db(self):
        """When no solutions exist, report should be empty."""
        Solution.objects.all().delete()
        url = reverse('aggregate-report')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class EquityDistributionExtendedTests(APITestCase):
    """Extended tests for the equity distribution endpoint."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', email='a@b.com', password='password123'
        )
        self.client.login(username='admin', password='password123')

    def test_equity_high_board(self):
        sol = Solution.objects.create(name="Equity High", flop_texture='High')
        url = reverse('solution-equity', args=[sol.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)
        # Hero should have advantage on High boards
        last_bin = response.data[-1]
        self.assertGreater(last_bin['hero'], last_bin['villain'])

    def test_equity_low_board(self):
        sol = Solution.objects.create(name="Equity Low", flop_texture='Low')
        url = reverse('solution-equity', args=[sol.id])
        response = self.client.get(url)
        last_bin = response.data[-1]
        # Villain has advantage on Low boards
        self.assertGreater(last_bin['villain'], last_bin['hero'])

    def test_equity_monotone_board(self):
        sol = Solution.objects.create(name="Equity Mono", flop_texture='Monotone')
        url = reverse('solution-equity', args=[sol.id])
        response = self.client.get(url)
        self.assertEqual(len(response.data), 10)

    def test_equity_nonexistent_solution(self):
        url = reverse('solution-equity', args=[9999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_equity_bin_labels(self):
        sol = Solution.objects.create(name="Equity Labels", flop_texture='Rainbow')
        url = reverse('solution-equity', args=[sol.id])
        response = self.client.get(url)
        labels = [d['bin'] for d in response.data]
        expected = ["0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
                    "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"]
        self.assertEqual(labels, expected)


class SolverConfigTests(APITestCase):
    """Test SolverConfig CRUD and relationship to Solutions."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', email='a@b.com', password='password123'
        )
        self.client.login(username='admin', password='password123')

    def test_create_solver_config(self):
        url = reverse('solverconfig-list')
        data = {
            'name': 'PioSolver Default',
            'solver_type': 'pio',
            'settings': {'accuracy': 0.01, 'max_iterations': 1000}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'PioSolver Default')

    def test_list_solver_configs(self):
        SolverConfig.objects.create(name='Config A', solver_type='pio')
        SolverConfig.objects.create(name='Config B', solver_type='gto+')
        url = reverse('solverconfig-list')
        response = self.client.get(url)
        self.assertEqual(len(response.data), 2)

    def test_solution_with_solver_config(self):
        config = SolverConfig.objects.create(
            name='Test Config', solver_type='pio',
            settings={'accuracy': 0.005}
        )
        sol = Solution.objects.create(
            name='Configured Solution', solver_config=config, stack_depth=100
        )
        url = reverse('solution-detail', args=[sol.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['solver_config'], config.id)
