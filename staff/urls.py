from django.urls import path

from .views import CreateStaffView, ChefTestView

urlpatterns = [

    path( "create/", CreateStaffView.as_view(), name="create-staff" ),
    path("chef-test/", ChefTestView.as_view(),name="chef-test" ),

]

