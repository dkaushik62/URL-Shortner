FROM gradle:8.14.3-jdk21
USER root
WORKDIR /workspace
COPY scenarios/starter/backend/build.gradle scenarios/starter/backend/settings.gradle scenarios/starter/backend/gradle.properties /workspace/
COPY scenarios/starter/backend/src /workspace/src
# Trusted, fixed manifests warm dependency caches before network-isolated runs.
RUN printf '%s\n' 'allprojects { tasks.register("warmDependencies") { doLast { configurations.findAll { it.canBeResolved }.each { it.resolve() } } } }' > /tmp/warm.gradle && gradle --no-daemon -I /tmp/warm.gradle warmDependencies test bootJar && rm -rf /workspace/build /workspace/src /tmp/warm.gradle
RUN mkdir -p /workspace/src && chown -R gradle:gradle /workspace /home/gradle
USER gradle
ENV GRADLE_USER_HOME=/home/gradle/.gradle
CMD ["gradle", "--offline", "--no-daemon", "test", "bootJar"]
