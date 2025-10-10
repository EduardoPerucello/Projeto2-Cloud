Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/focal64"
  config.vm.hostname = "exec-env"

  config.vm.provider "vmware_desktop" do |vmw|
    vmw..gui = true
    vmw.cpus = 2
    vmw.memory = 4096
  end

  config.vm.network "private_network", ip: "192.168.33.10"

  # Provisionamento
  config.vm.provision "shell", path: "provision.sh"
end
