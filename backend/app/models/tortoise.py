from tortoise import fields
from tortoise.models import Model


class TextSummary(Model):
    id = fields.IntField(pk=True)
    url = fields.TextField()
    summary = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    def __str__(self):
        return self.url