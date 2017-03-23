from django.db.models import (
    Model, CharField, ForeignKey, TextField, QuerySet, BigAutoField,
    BigIntegerField, AutoField, IntegerField, CASCADE,
)
from django.db.models.functions import Cast
from django.utils.translation import ugettext_lazy as _

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.search import SearchVectorField


class IndexQuerySet(QuerySet):
    def for_models(self, *models):
        content_types = ContentType.objects.get_for_models(*models).values()
        return self.filter(content_type__in=content_types)

    def for_objects(self, *objs):
        return (self.for_models(*{obj._meta.model for obj in objs})
                .filter(object_id__in=[str(obj.pk) for obj in objs]))

    def for_model(self, model):
        return self.filter(
            content_type=ContentType.objects.get_for_model(model))

    def for_object(self, obj):
        return self.for_model(obj._meta.model).filter(object_id=str(obj.pk))

    def for_queryset(self, queryset):
        return (
            self.for_model(queryset.model).filter(object_id__in=(
                queryset.annotate(text_pk=Cast('pk', TextField()))
                .values('text_pk'))))

    def pks(self):
        cast_field = self.model._meta.pk
        if isinstance(cast_field, BigAutoField):
            cast_field = BigIntegerField()
        elif isinstance(cast_field, AutoField):
            cast_field = IntegerField()
        return (self.annotate(typed_pk=Cast('object_id', cast_field))
                .values_list('typed_pk', flat=True))


class IndexEntry(Model):
    config = CharField(max_length=63, blank=True)

    content_type = ForeignKey(ContentType, on_delete=CASCADE)
    # We do not use an IntegerField since primary keys are not always integers.
    object_id = TextField()
    content_object = GenericForeignKey()

    title = TextField()
    body = TextField(blank=True)

    body_search = SearchVectorField()
    extra = JSONField(default=dict)

    objects = IndexQuerySet.as_manager()

    class Meta:
        unique_together = ('config', 'content_type', 'object_id')
        verbose_name = _('index entry')
        verbose_name_plural = _('index entries')

    def __str__(self):
        return '%s: %s' % (self.content_type.name, self.title)

    @property
    def model(self):
        return self.content_type.model
