"""Guards for APIs that touch the server machine's trading terminals."""
import ipaddress

from flask import current_app, has_request_context, jsonify, request


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def _host_without_port(host):
    if not host:
        return ""
    if host.startswith("["):
        return host.split("]", 1)[0] + "]"
    return host.rsplit(":", 1)[0].lower()


def _is_loopback(value):
    if not value:
        return False
    if value.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def allows_server_terminal_access():
    """Return True only when touching this machine's MT4/MT5 is intentional."""
    if current_app.config.get("ALLOW_SERVER_TERMINAL_CONNECT"):
        return True

    if not has_request_context():
        return False

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else request.remote_addr
    request_host = _host_without_port(request.host)

    return request_host in LOCAL_HOSTS and _is_loopback(client_ip)


def client_connector_required_response(platform):
    message = (
        f"{platform} 连接必须在登录系统的这台电脑上执行。"
        "服务器部署模式下，请在本机运行 client/start.bat 或对应客户端脚本，"
        "用 API Token 把本机 MT4/MT5 数据推送到服务器。"
    )
    return jsonify({
        "status": "client_connector_required",
        "package_installed": False,
        "terminal_running": False,
        "account_connected": False,
        "account": None,
        "message": message,
        "error": message,
    }), 409
