# -*- mode: ruby -*-
# vi: set ft=ruby :
#
# GitLab Lab : 2 VMs (gitlab + runner) provisionnées par Ansible.
# Hôte requis : Vagrant, VirtualBox, Ansible (Linux / macOS / WSL2).

GITLAB_IP  = ENV.fetch("GITLAB_IP", "192.168.56.10")
RUNNER_IP  = ENV.fetch("RUNNER_IP", "192.168.56.11")
GITLAB_RAM = ENV.fetch("GITLAB_RAM", "6144").to_i   # GitLab : 4 Go minimum
RUNNER_RAM = ENV.fetch("RUNNER_RAM", "3072").to_i
BOX        = ENV.fetch("LAB_BOX", "bento/ubuntu-22.04")

Vagrant.configure("2") do |config|
  config.vm.box = BOX
  config.vm.box_check_update = false

  # --- VM GitLab -------------------------------------------------------
  config.vm.define "gitlab" do |gl|
    gl.vm.hostname = "gitlab"
    gl.vm.network "private_network", ip: GITLAB_IP
    gl.vm.provider "virtualbox" do |vb|
      vb.name   = "lab-gitlab"
      vb.memory = GITLAB_RAM
      vb.cpus   = 4
    end
  end

  # --- VM Runner (définie en dernier : porte le provisioning Ansible) ---
  config.vm.define "runner" do |rn|
    rn.vm.hostname = "runner"
    rn.vm.network "private_network", ip: RUNNER_IP
    rn.vm.provider "virtualbox" do |vb|
      vb.name   = "lab-runner"
      vb.memory = RUNNER_RAM
      vb.cpus   = 2
    end

    # Un seul run Ansible, une fois les 2 VMs démarrées (limit = all)
    rn.vm.provision "ansible" do |ansible|
      ansible.playbook = "ansible/site.yml"
      ansible.limit    = "all"
      ansible.groups   = {
        "gitlab" => ["gitlab"],
        "runner" => ["runner"]
      }
      ansible.extra_vars = {
        "gitlab_ip" => GITLAB_IP,
        "runner_ip" => RUNNER_IP
      }
    end
  end
end
