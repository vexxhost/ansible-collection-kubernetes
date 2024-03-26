//  stages {
//    stage('upgrades') {
//      options {
//        timeout(time: 30, unit: 'MINUTES')
//      }
//      failFast false
def k8sUpgradeMaps = [['1.19.16', '1.20.15'], ['1.20.15', "1.21.14"],
["1.21.14", "1.22.17"], ["1.22.17", "1.23.17"], ["1.23.17", "1.24.17"],
["1.24.17", "1.25.16"], ["1.25.16", "1.26.11"], ["1.26.11", "1.27.8"], ["1.27.8", "1.28.4"]]

def integrationJobs = [:]
k8sUpgradeMaps.each { k8sUpgradeMap ->
    integrationJobs["upgrade-${k8sUpgradeMap[0]}-${k8sUpgradeMap[1]}"] = {
        timeout(30) {
            node('jammy-2c-8g') {
                checkout scm
                withEnv([
                    "OLD_KUBERNETES_VERSION=${k8sUpgradeMap[0]}",
                    "KUBERNETES_VERSION=${k8sUpgradeMap[1]}"
                ]) {
                    sh './.jenkins/upgrade.sh'
                }
            }
        }
    }
}

parallel integrationJobs
