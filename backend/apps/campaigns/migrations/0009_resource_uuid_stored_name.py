from pathlib import Path

from django.conf import settings
from django.db import migrations


def rename_resources_to_uuid(apps, schema_editor):
    """Los ficheros ya subidos se guardaron con un slug adivinable del
    nombre original (p.ej. informe_clientes_2026.pdf), servido sin
    autenticación en /recurso/<stored_name>/. Los renombra en disco y en BD
    al UUID del recurso para que las URLs antiguas dejen de ser adivinables.
    """
    Resource = apps.get_model('campaigns', 'Resource')
    resources_dir = Path(settings.MEDIA_ROOT) / 'resources'
    for resource in Resource.objects.all():
        old_name = resource.stored_name
        ext = Path(old_name).suffix.lower()
        new_name = f'{resource.id.hex}{ext}'
        if new_name == old_name:
            continue
        old_path = resources_dir / old_name
        new_path = resources_dir / new_name
        if old_path.exists():
            old_path.rename(new_path)
        resource.stored_name = new_name
        resource.save(update_fields=['stored_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0008_campaign_send_to_all'),
    ]

    operations = [
        migrations.RunPython(rename_resources_to_uuid, migrations.RunPython.noop),
    ]
