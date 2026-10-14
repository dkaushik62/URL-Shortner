FROM urlshortner-java-runner:local AS build
WORKDIR /app
COPY --chown=gradle:gradle . .
RUN --network=none gradle --offline --no-daemon test bootJar
FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=build /app/build/libs/app.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
