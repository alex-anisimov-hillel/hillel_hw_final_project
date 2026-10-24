from django.db import migrations


def create_default_warehouse(apps, schema_editor):
    from django.conf import settings

    Warehouse = apps.get_model("warehouse_mgmt", "Warehouse")
    Warehouse.objects.get_or_create(
        code=settings.DEFAULT_WAREHOUSE_CODE,
        defaults={"name": "Main warehouse", "priority": 10},
    )


class Migration(migrations.Migration):
    dependencies = [("warehouse_mgmt", "0001_initial")]
    operations = [migrations.RunPython(create_default_warehouse, migrations.RunPython.noop)]
