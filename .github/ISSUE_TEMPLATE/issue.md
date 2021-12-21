---
name: Issue
about: Create a report to help us improve

---

<!-- Before you open a new issue, search through the existing issues to see if others have had the same problem.

Issues not containing the minimum requirements will be closed:

- Issues without a description (using the header is not good enough) will be closed.
- Issues without debug logging will be closed.
- Issues without configuration will be closed

-->

## Version of the library
<!-- If you are not using the newest version, download and try that before opening an issue
If you are unsure about the version check the __version__.py file.
-->

## Logs

<!-- Add your logs here. ATTENTION: there may be personal information in your logs that you should mask by XXXXXX:
- appliance mac address; 
- serial number (there is mac address inside too)
- credentials/token should not be logged, but, please, double-check 
- local network IP address (please keep first octet(s) or use documentation network: e.g. 192.0.xx.xx) 
-->

```
Example log:
2021-12-31 23:59:00 example.com midea_beautiful_dehumidifier.scanner[25840] DEBUG Library version=0.1.0
2021-12-31 23:59:00 example.com midea_beautiful_dehumidifier.cloud[25840] Level 5 HTTP request user/login/id/get: {'appId': '1117', 'format': 2, 'clientType': 1, 'language': 'en_US', 'src': 17, 'stamp': '20211231235900', 'loginAccount': 'email@example.com', 'sign': 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'}
2021-12-31 23:59:00 example.com urllib3.connectionpool[123456] DEBUG Starting new HTTPS connection (1): mapp.appsmb.com:443



```

## Describe the bug
A clear and concise description of what the bug is.


