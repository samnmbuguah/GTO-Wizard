from django.db import models

class Solution(models.Model):
    name = models.CharField(max_length=255)
    rake = models.FloatField(null=True, blank=True)
    stack_depth = models.IntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    config = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
