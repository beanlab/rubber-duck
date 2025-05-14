from src.armory.stat_tools import plot_histogram
from src.utils.data_store import get_dataset


def main():
    data  = get_dataset("gestational")
    path = plot_histogram(data, "mage", "mage_histogram")
    print(f"Histogram saved at: {path}")


if __name__ == '__main__':
    main()
