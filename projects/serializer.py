from rest_framework import serializers
from .models import Projects, ProjectPhoto

class ProjectPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPhoto
        fields = ['id', 'image', 'caption', 'order']

class ProjectsSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    photos = ProjectPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Projects
        fields = ['id', 'name', 'year', 'category', 'technologies', 'description',
                 'created_at', 'updated_at', 'thumbnail_url', 'photos']

    def get_thumbnail_url(self, obj):
        if obj.thumbnail_image:
            return obj.thumbnail_image.url
        return None