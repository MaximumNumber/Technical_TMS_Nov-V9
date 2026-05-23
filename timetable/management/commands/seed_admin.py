from django.core.management.base import BaseCommand
import bcrypt
from timetable.models import UnifiedUser


class Command(BaseCommand):
    help = 'Create the default system manager admin account'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin', type=str)
        parser.add_argument('--password', default='admin123', type=str)
        parser.add_argument('--name', default='مدير النظام', type=str)

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        name = options['name']

        if UnifiedUser.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists — skipping.'))
            return

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = UnifiedUser.objects.create(
            username=username,
            full_name=name,
            email='admin@sust.edu',
            user_type='system_manager',
            password=hashed,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        user.set_unusable_password()  # Mark as using bcrypt only
        # Store bcrypt hash directly
        user.password = hashed
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f'✓ Created system manager: username="{username}" password="{password}"'
        ))
