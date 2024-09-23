from rest_framework import generics, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from core.models import Vehicle, Asset, Role
from .serializers import VehicleSerializer

class VehicleListCreateView(generics.ListCreateAPIView):
    serializer_class = VehicleSerializer

    def get_queryset(self):
        # Only return vehicles owned by the logged-in user
        return Vehicle.objects.filter(fleet__roles__user=self.request.user)

    def perform_create(self, serializer):
        fleet_id = self.request.data.get('fleet')  # Get the fleet ID from the request, 
        # Fleet ID is the ID of the asset when it is a vehicle asset
        fleet = get_object_or_404(Asset, id=fleet_id, asset_type='vehicle')

        # Check if the user is an admin of this fleet
        role = Role.objects.filter(user=self.request.user, asset=fleet, role='admin').exists()
        if not role:
            return Response({"error": "You are not authorized to add vehicles to this fleet."}, status=403)
        
        serializer.save(fleet=fleet)

class VehicleRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VehicleSerializer

    def get_queryset(self):
        # Ensure the user has permission to view/update/delete the vehicle
        vehicle_id = self.kwargs['pk']
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        fleet = vehicle.fleet
        role = Role.objects.filter(user=self.request.user, asset=fleet).exists()
        if self.request.method in ['PUT', 'DELETE']:
            # Only allow admins to update or delete vehicles
            is_admin = Role.objects.filter(user=self.request.user, asset=fleet, role='admin').exists()
            if not is_admin:
                return Response({"error": "You are not authorized to modify this vehicle."}, status=403)
        return Vehicle.objects.filter(id=vehicle_id)

class VehicleStatusView(generics.RetrieveAPIView):
    # Endpoint to retrieve vehicle status
    serializer_class = VehicleSerializer

    def get(self, request, *args, **kwargs):
        vehicle_id = self.kwargs['pk']
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)

        # Fetch status (e.g., location, number of passengers)
        # Assuming there is some status-related data in the `Vehicle` model, or you may need to add more fields.
        status_data = {
            'vehicle_number': vehicle.vehicle_number,
            'status': vehicle.status,
            # Add any other relevant data, such as location, num_passengers, etc.
        }
        return Response(status_data)
