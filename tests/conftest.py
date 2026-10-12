"""Normal test runs are offline; providers must use in-memory transports."""
import socket
import pytest


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    original_connect=socket.socket.connect
    def blocked_connect(sock,*args,**kwargs):
        if sock.family in {socket.AF_INET,socket.AF_INET6}:
            raise AssertionError("real network is disabled in the normal test suite")
        return original_connect(sock,*args,**kwargs)
    monkeypatch.setattr(socket.socket,"connect",blocked_connect)
    monkeypatch.setattr(socket.socket,"connect_ex",blocked_connect)
    monkeypatch.setattr(socket,"create_connection",lambda *a,**k: (_ for _ in ()).throw(AssertionError("network disabled")))
    monkeypatch.setattr(socket,"getaddrinfo",lambda *a,**k: (_ for _ in ()).throw(AssertionError("DNS disabled")))
    original_sendto=socket.socket.sendto
    def blocked_sendto(sock,*args,**kwargs):
        if sock.family in {socket.AF_INET,socket.AF_INET6}:
            raise AssertionError("UDP network disabled")
        return original_sendto(sock,*args,**kwargs)
    monkeypatch.setattr(socket.socket,"sendto",blocked_sendto)
