from .server import create_server


def main():
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
