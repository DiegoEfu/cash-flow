class StrAsNameMixin():
    """
    Summary:
    Simple mixin to return the name of the object when casted to str type. 

    Properties:
    - None

    Methods:
    - __str__(self) -> str: Returns the name of the object.
    """
    def __str__(self) -> str:
        return self.name