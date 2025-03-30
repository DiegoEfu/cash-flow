from django.shortcuts import render
from reports.pdf import *

# Create your views here.

def index(request):
    return generate_report(request)