pipeline {
  agent none

  options {
    disableConcurrentBuilds(abortPrevious: true);
  }
  stages {
    stage('upgrades') {
      options {
        timeout(time: 30, unit: 'MINUTES')
      }
      failFast false
      parallel {
        stage('upgrade-27-28') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.28.4"
            OLD_KUBERNETES_VERSION="1.27.8"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-26-27') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.27.8"
            OLD_KUBERNETES_VERSION="1.26.11"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-25-26') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.26.11"
            OLD_KUBERNETES_VERSION="1.25.16"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-24-25') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.25.16"
            OLD_KUBERNETES_VERSION="1.24.17"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-23-24') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.24.17"
            OLD_KUBERNETES_VERSION="1.23.17"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-22-23') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.23.17"
            OLD_KUBERNETES_VERSION="1.22.17"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-21-22') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.22.17"
            OLD_KUBERNETES_VERSION="1.21.14"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-20-21') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.21.14"
            OLD_KUBERNETES_VERSION="1.20.15"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
        stage('upgrade-19-20') {
          agent {
            label 'jammy-2c-8g'
          }
          environment {
            KUBERNETES_VERSION="1.20.15"
            OLD_KUBERNETES_VERSION="1.19.16"
          }
          steps {
            sh './.jenkins/upgrade.sh'
          }
        }
      }
    }
  }
}
