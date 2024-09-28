
# CGI-скрипт в Apache2

Flask может работать как CGI-скрипт в Apache2, что позволит запускать скрипт только при поступлении запроса, создавать ответ и завершаться, не занимая постоянно оперативную память. Это хорошее решение для редко используемых скриптов.


Код в файл `flask_cgi_backend.py`.

Сделайте его исполняемым:

```bash
chmod +x flask_cgi_backend.py
```

Нужно настроить Apache2 для работы с CGI-скриптами.

Вот шаги, которые нужно выполнить:

1. Убедитесь, что модуль CGI включен в Apache2:

```bash
sudo a2enmod cgi
```

2. Настройте виртуальный хост Apache2. Создайте файл (например, `/etc/apache2/sites-available/system-monitor.conf`) с следующим содержимым:

```apache
<VirtualHost *:80>
    ServerName your_domain.com
    DocumentRoot /path/to/your/system_monitor

    <Directory /path/to/your/system_monitor>
        Options +ExecCGI
        AddHandler cgi-script .py
        Require all granted
    </Directory>

    ScriptAlias / /path/to/your/system_monitor/flask_cgi_backend.py/

    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>

```

Замените `your_domain.com` на ваше доменное имя или IP-адрес, и `/path/to/your/system_monitor` на фактический путь к директории с вашими файлами.

3. Включите новый виртуальный хост:

```bash
sudo a2ensite system-monitor.conf
```

4. Перезапустите Apache2:

```bash
sudo systemctl restart apache2
```

Теперь, когда вы обращаетесь к вашему сайту, Apache2 будет запускать `flask_cgi_backend.py` как CGI-скрипт для каждого запроса. Скрипт будет выполняться, генерировать ответ и завершаться, не занимая постоянно оперативную память.

Обратите внимание на следующие моменты:

1. Убедитесь, что все необходимые Python-пакеты (Flask, psutil) установлены глобально или в виртуальном окружении, доступном для Apache2.

2. Права доступа: убедитесь, что Apache2 имеет права на выполнение вашего скрипта и чтение всех необходимых файлов.

3. Производительность: хотя этот метод экономит оперативную память, он может быть медленнее для частых запросов, так как каждый запрос запускает новый процесс Python. Но для редко используемого скрипта это не должно быть проблемой.

4. Отладка: в случае проблем проверьте логи Apache2 (`/var/log/apache2/error.log`).

Этот подход позволит вам использовать ваш Flask-скрипт как CGI в Apache2, экономя оперативную память, когда скрипт не используется.

