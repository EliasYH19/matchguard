// MatchGuard CI/CD pipeline
// Builds and tests both Flask microservices and the frontend image, same
// idea as the CI/CD lab session where we used Jenkins to build our Git
// project. Author: Elias
pipeline {
    agent any

    environment {
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install + Test: tournament-service') {
            steps {
                dir('services/tournament-service') {
                    sh 'python3 -m venv .venv'
                    sh '. .venv/bin/activate && pip install -r requirements.txt'
                    sh '. .venv/bin/activate && pytest ../../tests/test_tournament_service.py'
                }
            }
        }

        stage('Install + Test: scan-service') {
            steps {
                dir('services/scan-service') {
                    sh 'python3 -m venv .venv'
                    sh '. .venv/bin/activate && pip install -r requirements.txt'
                    sh '. .venv/bin/activate && pytest ../../tests/test_scan_service.py'
                }
            }
        }

        stage('Build images') {
            steps {
                sh 'docker build -t matchguard/tournament-service:$IMAGE_TAG services/tournament-service'
                sh 'docker build -t matchguard/scan-service:$IMAGE_TAG services/scan-service'
                sh 'docker build -t matchguard/frontend:$IMAGE_TAG frontend'
            }
        }

        stage('Push images') {
            when { branch 'main' }
            steps {
                sh 'docker tag matchguard/tournament-service:$IMAGE_TAG $REGISTRY/matchguard/tournament-service:$IMAGE_TAG'
                sh 'docker tag matchguard/scan-service:$IMAGE_TAG $REGISTRY/matchguard/scan-service:$IMAGE_TAG'
                sh 'docker tag matchguard/frontend:$IMAGE_TAG $REGISTRY/matchguard/frontend:$IMAGE_TAG'
                sh 'docker push $REGISTRY/matchguard/tournament-service:$IMAGE_TAG'
                sh 'docker push $REGISTRY/matchguard/scan-service:$IMAGE_TAG'
                sh 'docker push $REGISTRY/matchguard/frontend:$IMAGE_TAG'
            }
        }

        stage('Deploy to AKS') {
            when { branch 'main' }
            steps {
                sh 'kubectl apply -f k8s/namespace.yaml'
                sh 'kubectl apply -f k8s/azure-secret.yaml'
                sh 'kubectl apply -f k8s/tournament-service.yaml'
                sh 'kubectl apply -f k8s/scan-service.yaml'
                sh 'kubectl apply -f k8s/frontend.yaml'
                sh 'kubectl apply -f k8s/ingress.yaml'
                sh 'kubectl -n matchguard set image deployment/tournament-service tournament-service=$REGISTRY/matchguard/tournament-service:$IMAGE_TAG'
                sh 'kubectl -n matchguard set image deployment/scan-service scan-service=$REGISTRY/matchguard/scan-service:$IMAGE_TAG'
                sh 'kubectl -n matchguard set image deployment/frontend frontend=$REGISTRY/matchguard/frontend:$IMAGE_TAG'
            }
        }
    }

    post {
        always {
            echo "Build #${env.BUILD_NUMBER} finished with status: ${currentBuild.currentResult}"
        }
    }
}
