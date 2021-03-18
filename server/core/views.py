from ahj_gis.utils import filter_ahjs_by_location
from django.utils.http import urlsafe_base64_decode
from rest_framework.decorators import api_view
from .serializers import *
from rest_framework import generics
from .permissions import *
from rest_framework.response import Response
from .filters import *
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.authtoken.views import ObtainAuthToken
from .utils import *

import csv, io
from django.shortcuts import render, redirect
from django.contrib import messages


def ahj_upload(request):
    # declaring template
    template = "ahj_upload.html"
    data = AHJ.objects.all()
    # prompt is a context variable that can have different values      depending on their context
    prompt = {
        'order': 'Order of the CSV should be state_abbr, (city|county)_name',
        'profiles': data
              }
    # GET request returns the value of the data with the specified key.
    if request.method == "GET":
        return render(request, template, prompt)
    csv_file = request.FILES['file']
    # let's check if it is a csv file
    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'THIS IS NOT A CSV FILE')
    data_set = csv_file.read().decode('UTF-8')
    # setup a stream which is when we loop through each line we are able to handle a data in a stream
    io_string = io.StringIO(data_set)
    next(io_string)
    i = 1
    for column in csv.reader(io_string, delimiter=',', quotechar="|"):
        ahj = AHJ.objects.create(AHJName=column[1])
        address = Address.objects.create(AHJ=ahj, StateProvince=column[0])
        print(i)
        i += 1
    context = {}
    return render(request, template, context)


@api_view(['GET'])
def get_ahj_history(request, pk):
    if request.auth is None:
        return Response({'detail': 'No authentication provided'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        ahj = AHJ.objects.get(pk=pk)
    except AHJ.DoesNotExist:
        return Response({'detail': 'AHJ does not exist'})
#     return get_ahj_diff(ahj)


@api_view(['POST'])
def submit_edit(request):
    if request.auth is None:
        return Response({'detail': 'No authentication provided'}, status=status.HTTP_401_UNAUTHORIZED)
    return create_edit(request)


@api_view(['GET'])
def edit_detail(request, pk):
    if request.auth is None:
        return Response({'detail': 'No authentication provided'}, status=status.HTTP_401_UNAUTHORIZED)
    return set_edit(request, pk)


@api_view(['GET'])
def owner_to_ahj(request):
    if request.auth is None:
        return Response({'detail': 'No authentication provided'}, status=status.HTTP_401_UNAUTHORIZED)
    if not request.user.is_superuser:
        return Response('Unauthorized', status=status.HTTP_401_UNAUTHORIZED)
    mode = request.GET.get('mode')
    if mode is None:
        return Response('No mode specified', status=status.HTTP_400_BAD_REQUEST)
    user_id = request.GET.get('user')
    if user_id is None:
        return Response('No user specified', status=status.HTTP_400_BAD_REQUEST)
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return Response('User not found', status=status.HTTP_404_NOT_FOUND)
    AHJID = request.GET.get('AHJID')
    if AHJID is None:
        return Response('AHJID is required', status=status.HTTP_400_BAD_REQUEST)
    ahj = AHJ.objects.filter(AHJID=AHJID).first()
    if ahj is None:
        return Response('AHJ not found', status=status.HTTP_404_NOT_FOUND)

    if mode == 'add':
        user.AHJ.add(ahj)
    elif mode == 'remove':
        user.AHJ.remove(ahj)
    else:
        return Response('Invalid mode', status=status.HTTP_400_BAD_REQUEST)

    return Response('success', status=status.HTTP_200_OK)


class WebpageAHJList(generics.ListAPIView):
    queryset = AHJ.objects.all()
    serializer_class = AHJSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser)
    filter_backends = [SearchFilter, DjangoFilterBackend]
    filterset_class = AHJFilter
    search_fields = ['AHJName', 'address__City', 'address__County', 'address__Country', 'address__StateProvince', 'address__ZipPostalCode']

    def list(self, request, *args, **kwargs):
        """
        ListModelMixin: https://www.django-rest-framework.org/api-guide/generic-views/#listmodelmixin
        sends a response of a paginated list of AHJs with this JSON structure:
         - count: number of AHJs across all pages
         - next: the link to get the next page of AHJs (value null if no next page)
         - prev: the link to get the previous page (value null if no prev page)
         - results: list (or object containing the list) of serialized AHJ objects
        Default implementation: https://github.com/encode/django-rest-framework/blob/8351747d98b97907e6bb096914bf287a22c5314b/rest_framework/mixins.py#L33

        Filtering of AHJs by address happens here; other filtering is done in filters.py
        This method was overridden to include latlng results of the address provided.
        """
        queryset = self.filter_queryset(self.get_queryset())
        location = get_location(request)

        # filter by latlng if given
        if location['Latitude']['Value'] is not None and location['Longitude']['Value'] is not None:
            # mpoly of an AHJ refers to a Polygon object; mpoly of a Polygon refers to a MULTIPOLYGON
            # mpoly__mpoly__intersects looks for what AHJ's Polygon's MULTIPOLYGONS contain this point
            queryset = filter_ahjs_by_location(location['Longitude']['Value'], location['Latitude']['Value'],
                                               ahjs_to_search=queryset.values_list('AHJID', flat=True))

        # construct the paginated response
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)

            # passing data object including latlng for results
            return self.get_paginated_response({
                'Location': location,
                'ahjlist': serializer.data
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_serializer_context(self):
        return set_view_mode(self.request, hide_ui_fields=False, called_by_view=True)


class AHJList(generics.ListAPIView):
    queryset = AHJ.objects.all()
    serializer_class = AHJSerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)
    filter_class = AHJFilter
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['AHJID', 'AHJName', 'address__City', 'address__County', 'address__Country', 'address__StateProvince', 'address__ZipPostalCode']

    def list(self, request, *args, **kwargs):
        """
        ListModelMixin: https://www.django-rest-framework.org/api-guide/generic-views/#listmodelmixin
        sends a response of a paginated list of AHJs with this JSON structure:
         - count: number of AHJs across all pages
         - next: the link to get the next page of AHJs (value null if no next page)
         - prev: the link to get the previous page (value null if no prev page)
         - results: list (or object containing the list) of serialized AHJ objects
        Default implementation: https://github.com/encode/django-rest-framework/blob/8351747d98b97907e6bb096914bf287a22c5314b/rest_framework/mixins.py#L33

        Filtering of AHJs by address happens here; other filtering is done in filters.py
        This method was overridden to include latlng results of the address provided.
        """
        queryset = self.filter_queryset(self.get_queryset())
        location = get_location(request)

        # filter by latlng if given
        if location['Latitude']['Value'] is not None and location['Longitude']['Value'] is not None:
            # mpoly of an AHJ refers to a Polygon object; mpoly of a Polygon refers to a MULTIPOLYGON
            # mpoly__mpoly__intersects looks for what AHJ's Polygon's MULTIPOLYGONS contain this point
            queryset = filter_ahjs_by_location(location['Longitude']['Value'], location['Latitude']['Value'],
                                               ahjs_to_search=queryset.values_list('AHJID', flat=True))

        # construct the paginated response
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)

            # passing data object including latlng for results
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_serializer_context(self):
        return set_view_mode(self.request, hide_ui_fields=True, called_by_view=True)


class AHJDetail(generics.RetrieveAPIView):
    lookup_field = 'AHJID'
    queryset = AHJ.objects.all()
    serializer_class = AHJSerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)

    def get_serializer_context(self):
        return set_view_mode(self.request, hide_ui_fields=False, called_by_view=True)


class EditList(generics.ListAPIView):
    queryset = Edit.objects.all()
    serializer_class = EditSerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)
    filter_class = EditFilter


class AHJHistory(generics.ListAPIView):
    lookup_field = 'AHJID'
    queryset = AHJ.history.all()
    serializer_class = AHJHistorySerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['AHJID', 'AHJName']


class AddressHistory(generics.ListAPIView):
    queryset = Address.history.all()
    serializer_class = AddressHistorySerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['AHJ__AHJID', 'AHJ__AHJName', 'Contact__FirstName', 'Contact__MiddleName', 'Contact__LastName', 'Contact__id']


class ContactHistory(generics.ListAPIView):
    queryset = Contact.history.all()
    serializer_class = ContactHistorySerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['AHJ__AHJID', 'FirstName', 'LastName', 'id']


class EngineeringReviewRequirementHistory(generics.ListAPIView):
    queryset = EngineeringReviewRequirement.history.all()
    serializer_class = EngineeringReviewRequirementHistorySerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['AHJ__AHJID', 'EngineeringReviewType', 'RequirementLevel', 'StampType', 'id']


class LocationHistory(generics.ListAPIView):
    queryset = Location.history.all()
    serializer_class = LocationHistorySerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['Address__id']


class ObtainAuthTokenUserInfo(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super(ObtainAuthTokenUserInfo, self).post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        return Response({
                    'status': 'success',
                    'is_superuser': token.user.is_superuser,
                    'is_staff': token.user.is_staff,
                    'auth_token': token.key
                })


class CreateUser(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsSuperUserOrReadOnly)


@api_view(['GET'])
def activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        if user.is_active:
            user = None
            message = 'Success'
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
        message = 'User not found.'
    if user is not None and user.email_confirmation_token.check_token(user, token):
        user.is_active = True
        user.save()
        message = 'Success'
    return render(request, 'email_link_landing_page.html', {'message': message})


@api_view(['GET'])
def set_edit_status_email(request, uidb64, token, edit_id):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        edit = Edit.objects.get(pk=edit_id)
        message = 'Success'
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        edit = None
        user = None
        message = 'User or edit not found.'
    if user is not None and edit is not None and user.email_confirmation_token.check_token(user, token):
        if edit.IsConfirmed is not None:
            message = 'This edit has already been processed.'
        elif user.is_superuser or edit.is_record_owner(user.id):
            confirm_status = request.GET.get('confirm')
            if confirm_status == 'accepted':
                edit.accept(user.id)
            elif confirm_status == 'rejected':
                edit.reject(user.id)
            message = 'Success'
    return render(request, 'email_link_landing_page.html', {'message': message})
