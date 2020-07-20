from rest_framework.utils import json
from .utils import get_ahj_set, get_orange_button_value_primitive
from rest_framework.decorators import api_view
from core.models import AHJ
from core.serializers import AHJSerializer
from rest_framework.response import Response
from .constants import GOOGLE_GEOCODING_API_KEY
from googlemaps import Client

gmaps = Client(key=GOOGLE_GEOCODING_API_KEY)


@api_view(['POST'])
def find_ahj_coordinate(request):
    if request.auth is None:
        return Response(request.detail)

    if request.data.get('Location') is None:
        # The data is an Location
        location = request.data
    else:
        # The data is a Address
        location = request.data.get('Location')

    longitude = get_orange_button_value_primitive(location.get('Longitude', ''))
    latitude = get_orange_button_value_primitive(location.get('Latitude', ''))

    try:
        longitude = float(longitude)
        latitude = float(latitude)
    except (TypeError, ValueError):
        return Response({'detail': 'invalid coordinates'})

    ahj_set = get_ahj_set(longitude, latitude)

    return Response(AHJSerializer(ahj_set, many=True).data)


@api_view(['POST'])
def find_ahj_address(request):
    if request.auth is None:
        return Response(request.detail)

    addr_line_1 = get_orange_button_value_primitive(request.data.get('AddrLine1', ''))
    addr_line_2 = get_orange_button_value_primitive(request.data.get('AddrLine2', ''))
    addr_line_3 = get_orange_button_value_primitive(request.data.get('AddrLine3', ''))
    city = get_orange_button_value_primitive(request.data.get('City', ''))
    state_province = get_orange_button_value_primitive(request.data.get('StateProvince', ''))
    zip_postal_code = get_orange_button_value_primitive(request.data.get('ZipPostalCode', ''))

    geocode_result = gmaps.geocode(addr_line_1 + ' ' + addr_line_2 + ' ' + addr_line_3 + ', ' + city + ', ' + state_province + ' ' + zip_postal_code)
    print(geocode_result)
    # Find AHJ's for all possible address matches
    ahj_set = []
    for x in range(len(geocode_result)):
        coordinates = geocode_result[x]['geometry']['location']
        longitude = coordinates['lng']
        latitude = coordinates['lat']
        ahj_set += get_ahj_set(longitude, latitude)

    return Response(AHJSerializer(ahj_set, many=True).data)
