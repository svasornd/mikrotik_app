import configparser
import difflib
import paramiko
import sys
import re


def load_config(path="config.ini"):
    config = configparser.ConfigParser()
    config.read(path)
    return config


def get_config_via_ssh(host, username, password):
    print(f"Получение конфигурации с {host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=username, password=password)
    stdin, stdout, stderr = ssh.exec_command("/export")
    config_data = stdout.read().decode("utf-8")
    ssh.close()
    return config_data


def read_config_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_by_section(config_text):
    sections = {}
    current_section = None
    lines = config_text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith('/'):
            current_section = line
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)
    return sections

def join_continuation_lines(lines):
    joined = []
    buffer = ""
    for line in lines:
        if line.endswith("\\"):
            buffer += line[:-1]  # delete \
        else:
            buffer += line
            joined.append(buffer)
            buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def normalize_line(line):
    # replace mac-address in
    line = re.sub(r'(mac-address=)[0-9A-Fa-f:]+', r'\1xx:xx:xx:xx:xx:xx', line)
    # delete disabled=yes
    line = re.sub(r'(\s*)\bdisabled=yes\b(\s*)', lambda m: ' ' if m.group(1) and m.group(2) else '', line)
    # normalize space
    line = re.sub(r'\s+', ' ', line)
    # delete \r and space
    line = line.replace('\r', '').strip()
    return line.strip()

def compare_sections(old_sections, new_sections):
    all_keys = set(old_sections.keys()) | set(new_sections.keys())
    diffs = {}
    for section in sorted(all_keys):
        old = old_sections.get(section, [])
        new = new_sections.get(section, [])
        old = sorted(join_continuation_lines(old))
        new = sorted(join_continuation_lines(new))
        norm_old = [normalize_line(line) for line in old]
        norm_new = [normalize_line(line) for line in new]
        norm_old = sorted(norm_old)
        norm_new = sorted(norm_new)

        diff = list(difflib.unified_diff(norm_old, norm_new, fromfile='router1', tofile='router2', lineterm=''))
        if diff:
            diffs[section] = diff
    return diffs


def save_diff_to_file(diffs, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for section, diff in diffs.items():
            f.write(f"===== Section: {section} =====\n")
            for line in diff:
                clean_line = line
                if line.startswith('! '):
                    clean_line = line[2:]  # delete "!" in start string
                f.write(clean_line + "\n")
            f.write("\n")


def main():
    config = load_config()
    method = config["general"].get("method", "file")
    output_path = config["files"]["output_diff"]
    print(method)

    if method == "ssh":
        cfg1 = get_config_via_ssh(
            config["router1"]["host"],
            config["router1"]["username"],
            config["router1"]["password"]
        )
        cfg2 = get_config_via_ssh(
            config["router2"]["host"],
            config["router2"]["username"],
            config["router2"]["password"]
        )
    elif method == "file":
        cfg1 = read_config_file(config["files"]["old_config"])
        cfg2 = read_config_file(config["files"]["new_config"])
    else:
        print(f"❌ Неизвестный метод: {method}. Используйте 'ssh' или 'file'.")
        sys.exit(1)

    sections1 = split_by_section(cfg1)
    sections2 = split_by_section(cfg2)

    diffs = compare_sections(sections1, sections2)

    save_diff_to_file(diffs, output_path)
    print(f"Сравнение завершено. Различия сохранены в: {output_path}")


if __name__ == "__main__":
    main()
