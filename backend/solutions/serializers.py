from rest_framework import serializers
from .models import SolverConfig, Solution, StrategyNode, StrategyLock, StudySession

class SolverConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolverConfig
        fields = '__all__'

class SolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Solution
        fields = '__all__'

class StrategyNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyNode
        fields = '__all__'

class StrategyLockSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = StrategyLock
        fields = ['id', 'user', 'node', 'locked_actions', 'is_active', 'created_at', 'updated_at']

class StudySessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudySession
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']
