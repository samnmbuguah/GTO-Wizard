from django.db import models
from django.contrib.postgres.indexes import GinIndex

class SolverConfig(models.Model):
    name = models.CharField(max_length=255)
    solver_type = models.CharField(max_length=50, default='pio')
    settings = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            GinIndex(fields=['settings'], name='solverconfig_settings_gin'),
        ]

    def __str__(self):
        return self.name

class Solution(models.Model):
    name = models.CharField(max_length=255)
    rake = models.FloatField(default=0.0)
    ante = models.FloatField(default=0.0)
    game_type = models.CharField(max_length=50, default='6-Max')
    stack_depth = models.IntegerField(default=100)
    flop_texture = models.CharField(max_length=50, default='Rainbow', choices=[
        ('High', 'High Board'),
        ('Low', 'Low Board'),
        ('Paired', 'Paired Board'),
        ('Monotone', 'Monotone Board'),
        ('Rainbow', 'Rainbow Board'),
        ('Straight-Friendly', 'Straight-Friendly'),
    ])
    solver_config = models.ForeignKey(SolverConfig, null=True, blank=True, on_delete=models.SET_NULL, related_name='solutions')
    config = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            GinIndex(fields=['config'], name='solution_config_gin'),
            models.Index(fields=['game_type', 'stack_depth', 'ante']),
        ]

    def __str__(self):
        return self.name

class StrategyNode(models.Model):
    solution = models.ForeignKey(Solution, related_name='nodes', on_delete=models.CASCADE)
    path = models.CharField(max_length=1024, db_index=True)
    hand = models.CharField(max_length=10, db_index=True)
    actions = models.JSONField() # {"fold": 0.0, "call": 1.0}
    ev = models.FloatField(null=True, blank=True)
    equity = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['solution', 'path', 'hand']),
        ]
class StrategyLock(models.Model):
    user = models.ForeignKey('auth.User', related_name='strategy_locks', on_delete=models.CASCADE)
    node = models.ForeignKey(StrategyNode, related_name='locks', on_delete=models.CASCADE)
    locked_actions = models.JSONField() # {"fold": 0.0, "call": 1.0}
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'node')

    def __str__(self):
        return f"Lock on {self.node.hand} for {self.user.username}"
class StudySession(models.Model):
    user = models.ForeignKey('auth.User', related_name='study_sessions', on_delete=models.CASCADE)
    solution = models.ForeignKey(Solution, related_name='study_sessions', on_delete=models.CASCADE)
    correct_hands = models.FloatField(default=0)
    total_hands = models.IntegerField(default=0)
    streak = models.IntegerField(default=0)
    best_streak = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session for {self.user.username} - {self.solution.name} ({self.created_at.date()})"
