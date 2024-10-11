from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F
from django.db.models.functions import TruncDate
from core.models import Asset, Transaction
from datetime import datetime, date, timedelta
from django.utils import timezone
from decimal import Decimal
from calendar import monthrange

class IndexStats(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get all assets associated with the user
        user_assets = Asset.objects.filter(roles__user=user)

        # Total number of assets
        total_assets = user_assets.count()

        # Sum of total revenue for all assets
        total_revenue = user_assets.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')

        # Get the month and year from query parameters, default to current month
        today = timezone.now().date()
        year = int(request.query_params.get('year', today.year))
        month = int(request.query_params.get('month', today.month))

        # Determine the start and end dates for the specified month
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

        # Ensure we don't query future dates
        end_date = min(end_date, today)

        # Get daily revenue for each asset type
        revenue_data = (
            Transaction.objects
            .filter(
                asset__in=user_assets,
                payment_status='completed',
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date
            )
            .annotate(date=TruncDate('timestamp'))
            .values('date', 'asset__asset_type')
            .annotate(daily_revenue=Sum('amount'))
            .order_by('date', 'asset__asset_type')
        )

        # Organize data for the graph
        graph_data = {}
        asset_types = set(user_assets.values_list('asset_type', flat=True))
        
        # Initialize all dates with zero revenue for each asset type
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            graph_data[date_str] = {'date': date_str}
            for asset_type in asset_types:
                graph_data[date_str][asset_type] = 0.00
            current_date += timedelta(days=1)

        # Fill in actual revenue data
        for item in revenue_data:
            date_str = item['date'].strftime('%Y-%m-%d')
            asset_type = item['asset__asset_type']
            graph_data[date_str][asset_type] = float(item['daily_revenue'])

        # Convert graph_data to a list and sort by date
        graph_data_list = sorted(graph_data.values(), key=lambda x: x['date'])

        return Response({
            'total_assets': total_assets,
            'total_revenue': float(total_revenue),
            'revenue_graph_data': graph_data_list,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        })