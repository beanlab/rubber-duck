# Rubber Duck Documentation

Welcome to the Rubber Duck project! This documentation will help you get started with contributing to and using our
project.

## Table of Contents

- [Getting Started](docs/getting-started.md)
- [Deployment Guide](docs/deployment.md)

## Project Overview

Rubber Duck is a Discord bot that helps users in a variety of situations by acting as a rubber duck learning partner. It
uses AI to understand and respond to programming, physics, statistics, and math questions.

---

## Current Supported Ducks

### Standard Rubber Duck

This is a general-purpose Discord Bot trained to use Socratic questioning to walk users through the learning process,
helping them find answers to their own questions while providing minimal guidance.

### Stats Duck

This is a statistics-focused Discord Bot trained to perform code-based statistical analysis on a list of provided
datasets without interpreting results. It runs arbitrary code safely in a Docker container and only displays results.

### Registration Duck

This bot authenticates users and assigns appropriate Discord roles as defined in the server configuration settings.

### Review Duck

This bot collects previous conversations and allows specified users to give each a score from 1-5 along with a review.
This enables errors to be easily identified from users' feedback.

### Other Duck Definitions

Channel-specific duck definitions are also supported in the configuration files, allowing for a variety of features.
Current examples include an `assignment_feedback`, a duck that analyzes and gives feedback on a user's project report,
and an `emoji_duck` that communicates only in emojis. Each duck is built off of a "user-led" or "agent-led" conversation
style.

---

## Quick Start

1. Clone the repository
2. Set up your environment and learn how to deploy locally (see [Getting Started](docs/getting-started.md))
3. See how rubber duck is launched on the production stage (see [Development Guide](development.md))

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.
