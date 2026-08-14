rule Suspicious_Private_Key
{
    meta:
        description = "Detect embedded private keys"
        severity = "high"

    strings:
        $rsa = "-----BEGIN RSA PRIVATE KEY-----" ascii
        $ec = "-----BEGIN EC PRIVATE KEY-----" ascii
        $openssh = "-----BEGIN OPENSSH PRIVATE KEY-----" ascii
        $pk8 = "-----BEGIN PRIVATE KEY-----" ascii

    condition:
        any of them
}


rule Suspicious_Shell_Download_Execution
{
    meta:
        description = "Detect common download-and-execute shell patterns"
        severity = "high"

    strings:
        $curl = "curl " ascii nocase
        $wget = "wget " ascii nocase
        $bash = "| bash" ascii nocase
        $sh = "| sh" ascii nocase

    condition:
        ($curl or $wget) and ($bash or $sh)
}


rule Suspicious_Reverse_Shell
{
    meta:
        description = "Detect common reverse shell strings"
        severity = "critical"

    strings:
        $bash_tcp = "/dev/tcp/" ascii
        $nc_exec = "nc -e " ascii nocase
        $netcat_exec = "netcat -e " ascii nocase

    condition:
        any of them
}


rule Unexpected_Executable_ELF
{
    meta:
        description = "Detect ELF executables in model artifacts"
        severity = "high"

    condition:
        uint32(0) == 0x464c457f
}


rule Unexpected_Windows_PE
{
    meta:
        description = "Detect Windows PE executables"
        severity = "high"

    condition:
        uint16(0) == 0x5a4d
}
