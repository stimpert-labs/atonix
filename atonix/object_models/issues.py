# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from datetime import datetime

from pydantic import Field

from atonix.object_models.common import BaseAtonixModel


class BareIssue(BaseAtonixModel):
    """Bare reference to an issue."""

    id: str = Field(alias="Id")
    title: str = Field(alias="Title")


class IssueLinks(BaseAtonixModel):
    snapshot: str | None = Field(default=None, alias="Snapshot")


class Issue(BaseAtonixModel):
    """Full issue details."""

    id: str = Field(alias="Id")
    asset_id: str = Field(alias="AssetId")
    title: str = Field(alias="Title")
    short_summary: str | None = Field(default=None, alias="ShortSummary")
    full_summary: str | None = Field(default=None, alias="FullSummary")
    category_desc: str | None = Field(default=None, alias="CategoryDesc")
    category_id: int | None = Field(default=None, alias="CategoryId")
    changed_by: str | None = Field(default=None, alias="ChangedBy")
    change_date: datetime = Field(alias="ChangeDate")
    close_date: datetime | None = Field(default=None, alias="CloseDate")
    created_by: str | None = Field(default=None, alias="CreatedBy")
    create_date: datetime = Field(alias="CreateDate")
    impact: float | None = Field(default=None, alias="Impact")
    issue_class_type_desc: str | None = Field(default=None, alias="IssueClassTypeDesc")
    issue_status: str = Field(alias="IssueStatus")
    issue_type_desc: str | None = Field(default=None, alias="IssueTypeDesc")
    issue_cause_type_descs: list[str] = Field(default_factory=list, alias="IssueCauseTypeDescs")
    links: IssueLinks | None = Field(default=None, alias="Links")
    numeric_id: int | None = Field(default=None, alias="NumericId")
    priority: str | None = Field(default=None, alias="Priority")
    resolution_status: str | None = Field(default=None, alias="ResolutionStatus")
    resolve_by_date: datetime | None = Field(default=None, alias="ResolveByDate")
    scorecard: bool | None = Field(default=None, alias="Scorecard")


class IssueCreate(BaseAtonixModel):
    """Properties for creating new issue."""

    asset_id: str = Field(alias="AssetId")
    title: str = Field(alias="Title")
    category_desc: str = Field(alias="CategoryDesc")
    issue_class_type_desc: str = Field(alias="IssueClassTypeDesc")
    created_by: str | None = Field(default=None, alias="CreatedBy")
    full_summary: str | None = Field(default=None, alias="FullSummary")
    priority: str | None = Field(default=None, alias="Priority")
    resolution_status: str | None = Field(default=None, alias="ResolutionStatus")
    resolve_by_date: datetime | None = Field(default=None, alias="ResolveByDate")
    scorecard: bool | None = Field(default=None, alias="Scorecard")
    short_summary: str | None = Field(default=None, alias="ShortSummary")


class IssuePatch(BaseAtonixModel):
    """Properties that are allowed to be patched."""

    title: str | None = Field(default=None, alias="Title")
    short_summary: str | None = Field(default=None, alias="ShortSummary")
    full_summary: str | None = Field(default=None, alias="FullSummary")
    priority: str | None = Field(default=None, alias="Priority")
    resolve_by_date: datetime | None = Field(default=None, alias="ResolveByDate")
    scorecard: bool | None = Field(default=None, alias="Scorecard")
    resolution_status: str | None = Field(default=None, alias="ResolutionStatus")
    changed_by: str | None = Field(default=None, alias="ChangedBy")
    status: str | None = Field(default=None, alias="Status")
    issue_type_desc: str | None = Field(default=None, alias="IssueTypeDesc")


class IssueKeyword(BaseAtonixModel):
    """Keyword providing insight to the issue."""

    keyword_desc: str = Field(alias="KeywordDesc")
    created_by: str | None = Field(default=None, alias="CreatedBy")
    create_date: datetime | None = Field(default=None, alias="CreateDate")


class Attachment(BaseAtonixModel):
    """Attachment metadata."""

    filename: str = Field(alias="Filename")
    temporary_link: str = Field(alias="TemporaryLink")
    link_expiration_date: datetime = Field(alias="LinkExpirationDate")
    change_date: datetime | None = Field(default=None, alias="ChangeDate")


class IssueDiscussionEntryDetails(BaseAtonixModel):
    """Discussion Entry with attachments."""

    title: str = Field(alias="Title")
    contents: str = Field(alias="Contents")
    created_by: str = Field(alias="CreatedBy")
    create_date: datetime = Field(alias="CreateDate")
    changed_by: str | None = Field(default=None, alias="ChangedBy")
    change_date: datetime | None = Field(default=None, alias="ChangeDate")
    attachments: list[Attachment] = Field(default_factory=list, alias="Attachments")


class IssueDiscussionEntryCreate(BaseAtonixModel):
    """Properties for creating new discussion entry.

    ``attachment_files`` lists the file names (with extension) you intend to
    attach; the created entry returns a temporary upload link for each.
    """

    title: str = Field(alias="Title")
    contents: str = Field(alias="Contents")
    created_by: str | None = Field(default=None, alias="CreatedBy")
    attachment_files: list[str] = Field(default_factory=list, alias="AttachmentFiles")


class AttachmentUpload(BaseAtonixModel):
    """Temporary link for uploading an attachment file to a discussion entry."""

    filename: str = Field(alias="Filename")
    temporary_link: str = Field(alias="TemporaryLink")
    link_expiration_date: datetime | None = Field(default=None, alias="LinkExpirationDate")


class IssueDiscussionEntry(BaseAtonixModel):
    """Discussion entry as returned when it is created."""

    title: str = Field(alias="Title")
    contents: str = Field(alias="Contents")
    created_by: str | None = Field(default=None, alias="CreatedBy")
    create_date: datetime | None = Field(default=None, alias="CreateDate")
    changed_by: str | None = Field(default=None, alias="ChangedBy")
    change_date: datetime | None = Field(default=None, alias="ChangeDate")
    attachment_uploads: list[AttachmentUpload] = Field(default_factory=list, alias="AttachmentUploads")


class IssueResolutionStatus(BaseAtonixModel):
    """Resolution status type."""

    resolution_status: str = Field(alias="ResolutionStatus")
    display_order: int = Field(alias="DisplayOrder")
