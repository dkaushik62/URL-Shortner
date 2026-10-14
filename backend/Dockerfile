FROM urlshortner-java-runner:local AS build
USER root
WORKDIR /app
RUN chown gradle:gradle /app
COPY --chown=gradle:gradle . .
USER gradle
RUN --network=none gradle --offline --no-daemon test bootJar
FROM urlshortner-java-runtime:local
COPY --from=build /app/build/libs/app.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
