from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('myapp', '0057_storeprofile_manual_payment_received_at')]

    operations = [
        migrations.CreateModel(
            name='AIAccountMessageSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_template', models.TextField(default='✨ Your personal AI account has been successfully activated for {access_days} days! 🎉\nEnjoy access to powerful AI models, image and file uploads, and other premium features through your dedicated account. 🚀\n🔗 Login: https://www.vidhyora.online\n📧 Email: {email}\n🔑 Password: {password}\n📅 Validity: {access_days} days\n🔒 This is your private account, and no account sharing is required. Please use the service responsibly. Fair-use policies and platform limits may apply. ⚖️\n🛠️ If you face any login or technical issue, please contact us—we’re always happy to help. 🤝\n🌟 EduTrellis\n🌐 https://www.edutrellis.in\n📧 support@edutrellis.in 📞 Calling Support: 10 AM–7 PM 💬 WhatsApp Support Available')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'AI Account Message Settings',
                'verbose_name_plural': 'AI Account Message Settings',
            },
        ),
    ]
