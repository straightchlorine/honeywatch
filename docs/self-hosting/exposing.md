---
description: "Move your real SSH server off port 22, prove you can still log in, then hand the port to the Cowrie honeypot."
---

# Exposing Port 22

Everything so far was private. This page hands port 22 of a real machine to a
fake SSH server, which is the point of the project and also the step that can
lock you out for good.

!!! danger "Order matters"
    Your own SSH server is on port 22 right now, and it is the only way in.
    Move it first, prove the new port works from a second terminal, and only
    then give 22 to Cowrie. Before you start, have your provider's web console
    or rescue mode open in another tab.

## Move Your Real SSH Server

Pick a free port for `sshd`. The examples use `2022`. Do not use `2222`, which
is what the compose file publishes for Cowrie.

Make `sshd` listen on both ports first, verify the new one, then drop the old
one.

**1. Add the new port.** In `/etc/ssh/sshd_config` (or a file under
`/etc/ssh/sshd_config.d/`):

```text
Port 22
Port 2022
```

**2. Let it through both firewalls.** Forgetting either one gives you a
connection that just hangs.

| Layer | What to do |
| --- | --- |
| Host firewall | `sudo ufw allow 2022/tcp`, or `sudo firewall-cmd --permanent --add-port=2022/tcp && sudo firewall-cmd --reload` |
| Cloud firewall | Add an inbound TCP rule for 2022 in your provider's console |

**3. If SELinux is enforcing**, label the port:

```bash
sudo semanage port -a -t ssh_port_t -p tcp 2022
```

**4. Turn off password logins.** This machine is about to become a scanning
target. Confirm your key is in `~/.ssh/authorized_keys` and that you have
already logged in with it, then set:

```text
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
```

**5. Check the config, then reload.**

```bash
sudo sshd -t                  # no output means valid
sudo systemctl reload sshd    # the unit is "ssh" on Debian and Ubuntu
```

!!! warning "Socket activation ignores the Port line"
    Recent Debian and Ubuntu start SSH through `ssh.socket`, and then the port
    comes from the socket unit, not `sshd_config`. If
    `systemctl is-active ssh.socket` prints `active`, set the port with
    `sudo systemctl edit ssh.socket` (clear `ListenStream=` before adding the
    new one), then `daemon-reload` and restart the socket.

## Confirm You Can Still Get In

Leave your current terminal logged in. It is your way to fix it in case something
goes wrong.

In a second terminal:

```bash
ssh -p 2022 user@your-vps
```

If it hangs, a firewall is dropping the port. If it is refused, `sshd` is not
listening; check `sudo ss -lntp | grep sshd`. Fix it from the terminal you
kept open.

Once the second session works, remove the `Port 22` line, reload again, and
confirm from your laptop:

```bash
ssh -p 22 user@your-vps        # refused
ssh -p 2022 user@your-vps      # works
```

Only now is port 22 free.

## Point Port 22 at Cowrie

Cowrie listens on 2222 inside its container. What changes is the host port
published onto it. Edit the `docker-compose.override.yml` from
[Deploy the Stack](index.md):

```yaml title="docker-compose.override.yml"
services:
  cowrie:
    ports: !override
      - "22:2222"

  api:
    ports: !override
      - "127.0.0.1:5000:5000"

  dashboard:
    ports: !override
      - "127.0.0.1:8080:80"

  postgres:
    ports: !override
      - "127.0.0.1:5433:5432"
```

Only Cowrie's line changed. Keep the other three: without them the API,
dashboard and Postgres go back to `0.0.0.0` the next time those containers are
recreated.

Render the merged result and count the entries under each `ports:`:

```bash
docker compose config
```

One entry per service. Two means the `!override` tag is missing. Then apply:

```bash
docker compose up -d cowrie
```

`address already in use` means something is still on port 22, almost always an
`sshd` holding the old socket. Go back to the previous section.

## Check It From Outside

!!! warning "Your host firewall is probably not in front of the container"
    Docker installs published ports as DNAT rules ahead of the chains `ufw`
    and similar, so `ufw status` can say a port is denied while the
    container behind it answers the internet. Never verify exposure from the
    VPS itself.

From another machine:

```bash
nmap -Pn -p 22,2022,2222,5000,5433,8080 your-vps
```

| Port | Expected |
| --- | --- |
| 22 | Open, banner `SSH-2.0-OpenSSH_9.8p1 RHEL10`. That is Cowrie. |
| 2022 | Open, your real server's banner |
| 2222 | Closed. Open means the `!override` tag is missing and Cowrie is on both ports |
| 5000, 5433, 8080 | Closed or filtered |

If 5000, 5433 or 8080 answer, fix the override before going further. 5433 is
a live database.

Your cloud firewall needs the matching shape: inbound 22 from anywhere, inbound
2022 ideally from your own address only, everything else denied.

Finally, log in the way an attacker would:

```bash
ssh -p 22 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@your-vps
# password: changeme
```

The host-key flags matter here. Your `known_hosts` still holds your real
server's key for this address, and OpenSSH aborts with
`REMOTE HOST IDENTIFICATION HAS CHANGED` before asking for a password.

A `[root@centos ~]#` prompt means the whole path works, and that session is in
the dashboard within seconds.

## What Attackers See

Cowrie is an emulator. Commands are answered from a pickled fake filesystem
plus canned output; nothing an attacker types runs on your host.

The persona is deliberate, and every value is something a scanner can compare
against other boxes:

| Property | Value | Set in |
| --- | --- | --- |
| Hostname | `centos` | `cowrie/cowrie.cfg` |
| Prompt | `[root@centos ~]#` | `cowrie/cowrie.cfg` |
| Timezone | `Europe/Helsinki` | `cowrie/cowrie.cfg` |
| Kernel | `6.12.0-116.el10.x86_64` | `cowrie/cowrie.cfg` |
| SSH banner | `SSH-2.0-OpenSSH_9.8p1 RHEL10` | `cowrie/cowrie.cfg` |

The kernel string also appears in `cowrie/honeyfs/proc/version` and the
`hostnamectl` output under `cowrie/txtcmds`, and the machine ID is repeated in
four files including `cowrie/fs/build-centos-fs.sh`. Change all of them or
none, or the box contradicts itself the moment someone runs two commands.

**Credentials.** `cowrie/userdb.txt` is a curated weak list, not a wildcard:
`root:123456`, `root:admin`, `admin:admin`, `centos:centos`, `pi:raspberry`
and a handful more, ending in a rule that rejects everything else. `root:root`,
`root:toor`, `root:12345` and `root:password` are rejected on purpose, because a
box where 96 out of 100 sprayed credentials work is itself a hint that something
is up. Do not add a `/honeypot/i` reject rule; it is in Cowrie's upstream example
and scanners fingerprint it.

**Public address.** Inside the fake shell, `ifconfig` shows the container's
`172.x` NAT address unless you set `COWRIE_HONEYPOT_INTERNET_FACING_IP`. Only
the production compose file passes it through, so on this path add it to the
override, keeping the `ports:` entry:

```yaml title="docker-compose.override.yml (cowrie service only)"
services:
  cowrie:
    ports: !override
      - "22:2222"
    environment:
      COWRIE_HONEYPOT_INTERNET_FACING_IP: "203.0.113.10"
```

Leave it unset to let Cowrie guess. Never set it to an empty string; that
blanks the address in `ifconfig`, which is worse than the NAT one.

**Host key.** Cowrie keeps its host keys in an anonymous volume the image
declares. That survives `docker compose up` recreating the container, but
`docker compose down` throws it away and the next start generates a new key.
Returning scanners can notice. To pin it, add a named volume for
`/cowrie/cowrie-git/var/lib/cowrie` in your override, as the production file
does.

## If You Cannot Move Port 22

If `sshd` has to stay on 22, give Cowrie a second public address instead:

```yaml title="docker-compose.override.yml (cowrie service only)"
services:
  cowrie:
    ports: !override
      - "203.0.113.20:22:2222"
```

`sshd` must not be listening on that address. Pin it with `ListenAddress` for
the one you kept and confirm with `sudo ss -lntp`.

Some providers can also redirect a public port to another at the load balancer
or firewall. If yours does, point public 22 at whatever port Cowrie is
published on.

A host-level iptables redirect is possible, but Docker manages its own chains
and whether a hand-written DNAT rule lands before or after them decides
whether it works. The repo ships no such rule, so there is no tested recipe
here. If you build one, verify it from another machine.
