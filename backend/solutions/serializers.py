from rest_framework import serializers
from .models import Solution, StrategyNode

class SolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Solution
        fields = '__all__'

class StrategyNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyNode
        fields = '__all__'
